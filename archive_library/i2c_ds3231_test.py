from machine import I2C, Pin
import time
from i2c_ds3231 import DS3231
i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000)
rtc = DS3231(i2c, 0x68, 3, True, 'ntp')
rtc.save_time(True)
rtc.rtctime()
time.localtime()
