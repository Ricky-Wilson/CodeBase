function FindProxyForURL(url, host){if(host=='192.168.49.1') return 'DIRECT';else return "PROXY 192.168.49.1:8282; SOCKS5 192.168.49.1:8181; DIRECT";}