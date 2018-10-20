import machine
try:
   import utime as time
except:
   import time
try:
    import usocket as socket
except:
    import socket
try:
    import ustruct as struct
except:
    import struct
try:
    import uerrno as errno
except:
    import errno

# (date(2000, 1, 1) - date(1900, 1, 1)).days * 24*60*60
NTP_DELTA = 3155673600
# NTP server
host = "pool.ntp.org"

def getntp():
    print('Get UTC time from NTP server...')
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1b
   # Handling an unavailable NTP server error
    try:
        addr = socket.getaddrinfo(host, 123)[0][-1]
    except OSError: # as exc:
        #if exc.args[0] == -2:
            print('Connect NTP Server: Error resolving pool NTP')
            return 0
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1)
    res = s.sendto(NTP_QUERY, addr)
   # Handling NTP server long response error
    try:
        msg = s.recv(48)
    except OSError as exc:
        if exc.args[0] == errno.ETIMEDOUT:
            print('Connect NTP Server: Request Timeout')
            s.close()
            return 0
    s.close()
    val = struct.unpack("!I", msg[40:44])[0]
    return val - NTP_DELTA

# There's currently no timezone support in MicroPython, so
# utime.localtime() will return UTC time (as if it was .gmtime())
def settime():
   tm = time.localtime(getntp())
   tm = tm[0:3] + (0,) + tm[3:6] + (0,)
   machine.RTC().datetime(tm)
   print(time.localtime())
