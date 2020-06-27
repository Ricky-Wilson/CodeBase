"""Test the kernels service API."""
import json
import os
import shutil

from jupyterlab_launcher.tests.utils import LabTestBase, APITester
from notebook.tests.launchnotebook import assert_http_error


class SettingsAPI(APITester):
    """Wrapper for settings REST API requests"""

    url = 'lab/api/settings'

    def get(self, section_name):
        return self._req('GET', section_name)

    def put(self, section_name, body):
        return self._req('PUT', section_name, json.dumps(body))


class SettingsAPITest(LabTestBase):
    """Test the settings web service API"""

    def setUp(self):
        src = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            'schemas',
            '@jupyterlab')
        dst = os.path.join(self.lab_config.schemas_dir, '@jupyterlab')
        if not os.path.exists(dst):
            shutil.copytree(src, dst)
        self.settings_api = SettingsAPI(self.request)

    def test_get(self):
        id = '@jupyterlab/apputils-extension:themes'
        data = self.settings_api.get(id).json()

        assert data['id'] == id
        assert len(data['schema'])
        assert 'raw' in data

    def test_get_bad(self):
        with assert_http_error(404):
            self.settings_api.get('foo')

    def test_patch(self):
        id = '@jupyterlab/shortcuts-extension:plugin'

        assert self.settings_api.put(id, dict()).status_code == 204

    def test_patch_wrong_id(self):
        with assert_http_error(404):
            self.settings_api.put('foo', dict())

    def test_patch_bad_data(self):
        id = '@jupyterlab/codemirror-extension:commands'

        with assert_http_error(400):
            self.settings_api.put(id, dict(keyMap=10))
