


import subprocess
import json
import time
from math import floor




def scan_info():
    return json.loads(subprocess.getoutput('termux-wifi-scaninfo'))
    

def connection_info():
    return json.loads(subprocess.getoutput('termux-wifi-connectioninfo'))


def find_net(ssid):
    while 1:
        for net in scan_info():
            if net.get('ssid') == ssid:
                return net 
        

def test():
    signal_array = []
    while 1:
           
        target = 'DIRECT-Yz-Z3153V-PdaNet'
        net = find_net(target)
        rssi = abs(net.get('rssi'))
        
        signal_array.append(rssi)
        print(target)
        print(timestamp)
        print('RSSI: {}'.format(rssi))
        average_rssi = floor(sum(signal_array) / len(signal_array))
        print('Average RSSI: {}'.format(average_rssi))
        print('RSSI Samples: {}'.format(len(signal_array)))
        time.sleep(3)
        print('\n')
    

        
        
        

rssi_samples = []
speed_samples = []



while 1:
    info = connection_info()
    ssid = info.get('ssid')
    rssi = abs(info.get('rssi'))
    speed = info.get('link_speed_mbps')
    rssi_samples.append(rssi)
    speed_samples.append(speed)
    sample_count = len(rssi_samples)
    average_rssi = sum(rssi_samples) / sample_count
    average_speed = sum(speed_samples) / sample_count
    print(ssid)
    
    print('RSSI: {}'.format(rssi))
    print('Speed {} Mbps'.format(speed))
    print('Average RSSI: {0:.2f}'.format(average_rssi))  
    print('Average Speed: {0:.2f}'.format(average_speed)) 
    print('{} Samples.\n'.format(sample_count))