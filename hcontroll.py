import network, os
from json import dump, loads
from gc import collect
from os import stat
import uasyncio as asyncio
collect()                                                               #Очищаем RAM

config = {}                                                             #Основное хранилище настроек

def str_to_bool(s):
    if s == 'True':
         return True
    elif s == 'False':
         return False
    else:
         raise ValueError


def bool_to_str(s):
    if s == True:
        return 'ON'
    elif s == False:
        return 'OFF'


def read_write_root(passwd=None):
    if passwd:
        print('Create new root.txt file')
        with open('root.txt', 'w') as f:
            f.write(passwd)
    else:
        with open('root.txt') as f:
            return f.readline().rstrip()


def read_write_config(cfg=None):
    if cfg:
        print('Create new config.txt file')
        with open('config.txt', 'w') as f:
            dump(cfg, f)
    else:
        with open('config.txt', 'r') as f:
            return loads(f.read())


def update_config(mode=None, ssid=None, pssw=None, tz=None, \
                    dts=None, settm=None, pwr=None, ton=None, toff=None, work=None, 
                    rw=None):
    conf = read_write_config()
    collect()                                                        #Очищаем RAM
    if rw == 'w':
        conf['MODE'] = mode if mode else conf['MODE']         # Режим работы WiFi AP или ST
        conf['ssid'] = ssid if ssid else conf['ssid']                   # SSID для подключения к WiFi
        conf['pass'] = pssw if pssw else conf['pass']             # Пароль для подключения к WiFi
        conf['timezone'] = int(tz) if tz else conf['timezone']          # Временная зона
        conf['DST'] = str_to_bool(dts) if dts else conf['DST']          # Переход с летнего на зимнее время
        conf['SET'] = settm if settm else conf['SET']         # Температура в помещении при которой включиться отопление
        conf['DAY'] = pwr if pwr else conf['DAY']           # Уменьшение мощности в дневное время в %
        conf['ON'] = ton if ton else conf['ON']               # Время включения при работе по расписанию
        conf['OFF'] = toff if toff else conf['OFF']           # Время выключения при работе по расписанию
        conf['WORK'] = work if work else conf['WORK']  # Режим работы
        read_write_config(cfg=conf)
    config['MODE'] = conf['MODE']
    config['ssid'] = conf['ssid']
    config['pass'] = conf['pass']
    config['timezone'] = conf['timezone']
    config['DST'] = conf['DST']
    config['SET'] = conf['SET']
    config['DAY'] = conf['DAY']
    config['ON'] = conf['ON']
    config['OFF'] = conf['OFF']
    config['WORK'] = conf['WORK']
    config['DS_K'] = conf['DS_K']
    collect()                                                        #Очищаем RAM


#Базовый класс
class HeatControlBase:
    def __init__(self, config):
        self.config = config


    #Проверяем наличие файлов
    def exists(self, path):
        try:
            stat(path)
        except OSError:
            return False
        return True


    #Выводим отладочные сообщения
    def dprint(self, *args):
        if self.config['DEBUG']:
            print(*args)


    #Настройка для режима Точка доступа и подключения к сети WiFi
    def _con(self):
        if self.config['MODE'] == 'AP':
            self.config['WIFI'].active(True)
            #Устанавливаем SSID и пароль для подключения к Точке доступа
            self.config['WIFI'].config(essid=self.config['ssid'], password=self.config['pass'])
            #Устанавливаем статический IP адрес, шлюз, dns
            self.config['WIFI'].ifconfig(self.config['WIFI_AP'])
        elif self.config['MODE'] == 'ST':
            self.config['WIFI'].active(True)
            network.phy_mode(1) # network.phy_mode = MODE_11B
            #Подключаемся к WiFi сети
            self.config['WIFI'].connect(self.config['ssid'], self.config['pass'])


    #Подключение к сети WiFi или поднятие точки доступа
    async def connect_wf(self):
        if self.config['MODE'] == 'AP': #Если точка доступа
            self.dprint('WiFi AP Mode!')
            self._con() #Настройка для режима Точка доступа и подключения к сети WiFi
            if self.config['WIFI'].status() == -1:
                self.dprint('WiFi: AP Mode OK!')
                self.config['IP'] = self.config['WIFI'].ifconfig()[0]
                self.dprint('WiFi:', self.config['IP'])
                self.config['no_wifi'] = 'AP'
        elif self.config['MODE'] == 'ST': #Если подключаемся к сети
            self.dprint('Connecting to WiFi...')
            self._con() #Настройка для режима Точка доступа и подключения к сети WiFi
            if self.config['WIFI'].status() == network.STAT_CONNECTING:
                self.dprint('WiFi: Waiting for connection to...')
            # Задержка на соединение, если не успешно, будет выдана одна из ошибок
            # Выполнение условия проверяем каждую секунду, задержка для получения IP адреса от DHCP
            while self.config['WIFI'].status() == network.STAT_CONNECTING:
                await asyncio.sleep(1)
            #Соединение успешно установлено
            if self.config['WIFI'].status() == network.STAT_GOT_IP:
                self.dprint('WiFi: Connection successfully!')
                self.config['IP'] = self.config['WIFI'].ifconfig()[0]
                self.dprint('WiFi:', self.config['IP'])
                self.config['no_wifi'] = False #Сообщаем, что соединение успешно установлено
            #Если соединение по каким-то причинам не установлено
            if not self.config['WIFI'].isconnected():
                self.config['no_wifi'] = True #Сообщаем, что соединение не установлено
                self.dprint('WiFi: Connection unsuccessfully!')
            #self._error_con() #Выводим сообщения, о причинах отсутствия соединения


    #Переподключаемся к сети WiFi
    async def reconnect(self):
        self.dprint('Reconnecting to WiFi...')
        #Сбрасываем IP адрес к виду 0.0.0.0
        self.config['IP'] = self.config['WIFI'].ifconfig()[0]
        #Разрываем соединение, если они не разорвано
        self.config['WIFI'].disconnect()
        await asyncio.sleep(1)
        self._con() #Настройка для режима Точка доступа и подключения к сети WiFi
        # Задержка на соединение, если не успешно, будет выдана одна из ошибок
        # Выполнение условия проверяем каждые 20 милисекунд, задержка для получения IP адреса от DHCP
        while self.config['WIFI'].status() == network.STAT_CONNECTING:
            await asyncio.sleep_ms(20)
        #Если соединение установлено
        if self.config['WIFI'].status() == network.STAT_GOT_IP:
            #Сохраняем новый IP адрес
            self.config['IP'] = self.config['WIFI'].ifconfig()[0]
            self.config['no_wifi'] = False #Сообщаем, что соединение успешно установлено
            self.dprint('WiFi: Reconnecting successfully!')
            self.dprint('WiFi:', self.config['IP'])
        #self._error_con() #Выводим сообщения, о причинах отсутствия соединения
        #Если по какой-то причине соединение не установлено
        if not self.config['WIFI'].isconnected():
            self.config['no_wifi'] = True #Сообщаем, что соединение не установлено
            self.dprint('WiFi: Reconnecting unsuccessfully!')
        await asyncio.sleep(1)


class HeatControl(HeatControlBase):
    def __init__(self):
        super().__init__(config)


    #Проверка соединения с Интернетом
    async def _check_wf(self):
        while True:
            if not self.config['no_wifi']:                      #Если оединение установлено
                if self.config['WIFI'].status() == network.STAT_GOT_IP: #Проверяем наличие соединения
                    await asyncio.sleep(1)
                else:                                                   #Если соединение отсутсвует или оборвано
                    await asyncio.sleep(1)
                    self.config['no_wifi'] = True               #Сообщаем, что соединение оборвано
            else:                                                       #Если соединение отсутсвует
                await asyncio.sleep(1)
                await self.reconnect()                                  #Переподключаемся
        await asyncio.sleep(1)
        collect()                                                    #Очищаем RAM


    #Подключаемся к WiFi или поднимаем точку доступа
    async def connect(self):
        await self.connect_wf()                                         #Подключение или точка доступа, зависит от настройки
        if self.config['MODE'] == 'ST':
            loop = asyncio.get_event_loop()
            loop.create_task(self._check_wf())
        elif self.config['MODE'] == 'AP':
            collect()                                                #Очищаем RAM
    
