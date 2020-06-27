#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  smoke_zephyr/job.py
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following disclaimer
#    in the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of the project nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import datetime
import logging
import threading
import time
import uuid

__all__ = ['JobManager', 'JobRequestDelete']

def normalize_job_id(job_id):
	"""
	Convert a value to a job id.

	:param job_id: Value to convert.
	:type job_id: int, str
	:return: The job id.
	:rtype: :py:class:`uuid.UUID`
	"""
	if not isinstance(job_id, uuid.UUID):
		job_id = uuid.UUID(job_id)
	return job_id

class JobRequestDelete(object):
	"""
	An instance of this class can be returned by a job callback to request
	that the job be deleted and not executed again.
	"""
	pass

class JobRun(threading.Thread):
	def __init__(self, callback, args):
		super(JobRun, self).__init__()
		self.daemon = False
		self.callback = callback
		self.callback_args = args
		self.request_delete = False
		self.exception = None
		self.reaped = False

	def run(self):
		try:
			result = self.callback(*self.callback_args)
			if isinstance(result, JobRequestDelete):
				self.request_delete = True
		except Exception as error:
			self.exception = error
		return

# Job Dictionary Details:
#   last_run: datetime.datetime
#   run_every: datetime.timedelta
#   job: None or JobRun instance
#   callback: function
#   parameters: list of parameters to be passed to the callback function
#   enabled: boolean if false do not run the job
#   tolerate_exceptions: boolean if true this job will run again after a failure
#   run_count: number of times the job has been ran
#   expiration: number of times to run a job, datetime.timedelta instance or None
class JobManager(object):
	"""
	This class provides a threaded job manager for periodically executing
	arbitrary functions in an asynchronous fashion.
	"""
	def __init__(self, use_utc=True, logger_name=None):
		"""
		:param bool use_utc: Whether or not to use UTC time internally.
		:param str logger_name: A specific name to use for the logger.
		"""
		self._thread = threading.Thread(target=self._run)
		self._thread.daemon = True
		self._jobs = {}
		self._thread_running = threading.Event()
		self._thread_shutdown = threading.Event()
		self._thread_shutdown.set()
		self._job_lock = threading.RLock()
		self.use_utc = use_utc
		self.logger = logging.getLogger(logger_name or self.__class__.__name__)
		self.exc_info = False

	def __len__(self):
		return self.job_count()

	def _job_execute(self, job_id):
		self._job_lock.acquire()
		job_desc = self._jobs[job_id]
		job_desc['last_run'] = self.now()
		job_desc['run_count'] += 1
		self.logger.debug('executing job with id: ' + str(job_id) + ' and callback function: ' + job_desc['callback'].__name__)
		job_desc['job'] = JobRun(job_desc['callback'], job_desc['parameters'])
		job_desc['job'].start()
		self._job_lock.release()

	def _run(self):
		self.logger.info('the job manager has been started')
		self._thread_running.set()
		self._thread_shutdown.clear()
		self._job_lock.acquire()
		while self._thread_running.is_set():
			self._job_lock.release()
			time.sleep(1)
			self._job_lock.acquire()
			if not self._thread_running.is_set():
				break

			# reap jobs
			jobs_for_removal = set()
			for job_id, job_desc in self._jobs.items():
				job_obj = job_desc['job']
				if job_obj.is_alive() or job_obj.reaped:
					continue
				if job_obj.exception is not None:
					if job_desc['tolerate_exceptions']:
						self.logger.warning('job ' + str(job_id) + ' encountered exception: ' + job_obj.exception.__class__.__name__, exc_info=self.exc_info)
					else:
						self.logger.error('job ' + str(job_id) + ' encountered an error and is not set to tolerate exceptions', self.exc_info)
						jobs_for_removal.add(job_id)
				if isinstance(job_desc['expiration'], int):
					if job_desc['expiration'] <= 0:
						jobs_for_removal.add(job_id)
					else:
						job_desc['expiration'] -= 1
				elif isinstance(job_desc['expiration'], datetime.datetime):
					if self.now_is_after(job_desc['expiration']):
						jobs_for_removal.add(job_id)
				if job_obj.request_delete:
					jobs_for_removal.add(job_id)
				job_obj.reaped = True
			for job_id in jobs_for_removal:
				self.job_delete(job_id)

			# sow jobs
			for job_id, job_desc in self._jobs.items():
				if job_desc['last_run'] is not None and self.now_is_before(job_desc['last_run'] + job_desc['run_every']):
					continue
				if job_desc['job'].is_alive():
					continue
				if not job_desc['job'].reaped:
					continue
				if not job_desc['enabled']:
					continue
				self._job_execute(job_id)
		self._job_lock.release()
		self._thread_shutdown.set()

	def now(self):
		"""
		Return a :py:class:`datetime.datetime` instance representing the current time.

		:rtype: :py:class:`datetime.datetime`
		"""
		if self.use_utc:
			return datetime.datetime.utcnow()
		else:
			return datetime.datetime.now()

	def now_is_after(self, dt):
		"""
		Check whether the datetime instance described in dt is after the
		current time.

		:param dt: Value to compare.
		:type dt: :py:class:`datetime.datetime`
		:rtype: bool
		"""
		return bool(dt <= self.now())

	def now_is_before(self, dt):
		"""
		Check whether the datetime instance described in dt is before the
		current time.

		:param dt: Value to compare.
		:type dt: :py:class:`datetime.datetime`
		:rtype: bool
		"""
		return bool(dt >= self.now())

	def start(self):
		"""
		Start the JobManager thread.
		"""
		if self._thread_running.is_set():
			raise RuntimeError('the JobManager has already been started')
		self._thread.start()
		self._thread_running.wait()
		return

	def stop(self):
		"""
		Stop the JobManager thread.
		"""
		self.logger.debug('stopping the job manager')
		self._thread_running.clear()
		self._thread_shutdown.wait()
		self._job_lock.acquire()
		self.logger.debug('waiting on ' + str(len(self._jobs)) + ' job threads')
		for job_desc in self._jobs.values():
			if job_desc['job'] is None:
				continue
			if not job_desc['job'].is_alive():
				continue
			job_desc['job'].join()

		# the job lock must be released before the thread can be joined because the thread routine acquires it before
		# checking if it should exit, see https://github.com/zeroSteiner/smoke-zephyr/issues/4 for more details
		self._job_lock.release()
		self._thread.join()

		self.logger.info('the job manager has been stopped')
		return

	def job_run(self, callback, parameters=None):
		"""
		Add a job and run it once immediately.

		:param function callback: The function to run asynchronously.
		:param parameters: The parameters to be provided to the callback.
		:type parameters: list, tuple
		:return: The job id.
		:rtype: :py:class:`uuid.UUID`
		"""
		if not self._thread_running.is_set():
			raise RuntimeError('the JobManager is not running')
		parameters = (parameters or ())
		if not isinstance(parameters, (list, tuple)):
			parameters = (parameters,)
		job_desc = {}
		job_desc['job'] = JobRun(callback, parameters)
		job_desc['last_run'] = None
		job_desc['run_every'] = datetime.timedelta(0, 1)
		job_desc['callback'] = callback
		job_desc['parameters'] = parameters
		job_desc['enabled'] = True
		job_desc['tolerate_exceptions'] = False
		job_desc['run_count'] = 0
		job_desc['expiration'] = 0
		job_id = uuid.uuid4()
		self.logger.info('adding new job with id: ' + str(job_id) + ' and callback function: ' + callback.__name__)
		with self._job_lock:
			self._jobs[job_id] = job_desc
			self._job_execute(job_id)
		return job_id

	def job_add(self, callback, parameters=None, hours=0, minutes=0, seconds=0, tolerate_exceptions=True, expiration=None):
		"""
		Add a job to the job manager.

		:param function callback: The function to run asynchronously.
		:param parameters: The parameters to be provided to the callback.
		:type parameters: list, tuple
		:param int hours: Number of hours to sleep between running the callback.
		:param int minutes: Number of minutes to sleep between running the callback.
		:param int seconds: Number of seconds to sleep between running the callback.
		:param bool tolerate_execptions: Whether to continue running a job after it has thrown an exception.
		:param expiration: When to expire and remove the job. If an integer
			is provided, the job will be executed that many times.  If a
			datetime or timedelta instance is provided, then the job will
			be removed after the specified time.
		:type expiration: int, :py:class:`datetime.timedelta`, :py:class:`datetime.datetime`
		:return: The job id.
		:rtype: :py:class:`uuid.UUID`
		"""
		if not self._thread_running.is_set():
			raise RuntimeError('the JobManager is not running')
		parameters = (parameters or ())
		if not isinstance(parameters, (list, tuple)):
			parameters = (parameters,)
		job_desc = {}
		job_desc['job'] = JobRun(callback, parameters)
		job_desc['last_run'] = None
		job_desc['run_every'] = datetime.timedelta(0, ((hours * 60 * 60) + (minutes * 60) + seconds))
		job_desc['callback'] = callback
		job_desc['parameters'] = parameters
		job_desc['enabled'] = True
		job_desc['tolerate_exceptions'] = tolerate_exceptions
		job_desc['run_count'] = 0
		if isinstance(expiration, int):
			job_desc['expiration'] = expiration
		elif isinstance(expiration, datetime.timedelta):
			job_desc['expiration'] = self.now() + expiration
		elif isinstance(expiration, datetime.datetime):
			job_desc['expiration'] = expiration
		else:
			job_desc['expiration'] = None
		job_id = uuid.uuid4()
		self.logger.info('adding new job with id: ' + str(job_id) + ' and callback function: ' + callback.__name__)
		with self._job_lock:
			self._jobs[job_id] = job_desc
		return job_id

	def job_count(self):
		"""
		Return the number of jobs.

		:return: The number of jobs.
		:rtype: int
		"""
		return len(self._jobs)

	def job_count_enabled(self):
		"""
		Return the number of enabled jobs.

		:return: The number of jobs that are enabled.
		:rtype: int
		"""
		enabled = 0
		for job_desc in self._jobs.values():
			if job_desc['enabled']:
				enabled += 1
		return enabled

	def job_enable(self, job_id):
		"""
		Enable a job.

		:param job_id: Job identifier to enable.
		:type job_id: :py:class:`uuid.UUID`
		"""
		job_id = normalize_job_id(job_id)
		with self._job_lock:
			job_desc = self._jobs[job_id]
			job_desc['enabled'] = True

	def job_disable(self, job_id):
		"""
		Disable a job. Disabled jobs will not be executed.

		:param job_id: Job identifier to disable.
		:type job_id: :py:class:`uuid.UUID`
		"""
		job_id = normalize_job_id(job_id)
		with self._job_lock:
			job_desc = self._jobs[job_id]
			job_desc['enabled'] = False

	def job_delete(self, job_id, wait=True):
		"""
		Delete a job.

		:param job_id: Job identifier to delete.
		:type job_id: :py:class:`uuid.UUID`
		:param bool wait: If the job is currently running, wait for it to complete before deleting it.
		"""
		job_id = normalize_job_id(job_id)
		self.logger.info('deleting job with id: ' + str(job_id) + ' and callback function: ' + self._jobs[job_id]['callback'].__name__)
		job_desc = self._jobs[job_id]
		with self._job_lock:
			job_desc['enabled'] = False
			if wait and self.job_is_running(job_id):
				job_desc['job'].join()
			del self._jobs[job_id]

	def job_exists(self, job_id):
		"""
		Check if a job identifier exists.

		:param job_id: Job identifier to check.
		:type job_id: :py:class:`uuid.UUID`
		:rtype: bool
		"""
		job_id = normalize_job_id(job_id)
		return job_id in self._jobs

	def job_is_enabled(self, job_id):
		"""
		Check if a job is enabled.

		:param job_id: Job identifier to check the status of.
		:type job_id: :py:class:`uuid.UUID`
		:rtype: bool
		"""
		job_id = normalize_job_id(job_id)
		job_desc = self._jobs[job_id]
		return job_desc['enabled']

	def job_is_running(self, job_id):
		"""
		Check if a job is currently running. False is returned if the job does
		not exist.

		:param job_id: Job identifier to check the status of.
		:type job_id: :py:class:`uuid.UUID`
		:rtype: bool
		"""
		job_id = normalize_job_id(job_id)
		if job_id not in self._jobs:
			return False
		job_desc = self._jobs[job_id]
		if job_desc['job']:
			return job_desc['job'].is_alive()
		return False
