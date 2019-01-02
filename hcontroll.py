import gc, network, os
import uasyncio as asyncio
gc.collect()                                #Очищаем RAM

config = {}                                 #Основное хранилище настроек

#Базовый класс
class HeatControlBase:
    DEBUG = False
    def __init__(self, config):
        self.config = config


    #Проверяем наличие файлов
    def exists(self, path):
        try:
            os.stat(path)
        except OSError:
            return False
        return True


    #Выводим отладочные сообщения
    def dprint(self, *args):
        if self.DEBUG:
            print(*args)


    #Настройка для режима Точка доступа и подключения к сети WiFi
    def _con(self):
        if self.config['MODE_WiFi'] == 'AP':
            self.config['WIFI'].active(True)
            #Устанавливаем SSID и пароль для подключения к Точке доступа
            self.config['WIFI'].config(essid=self.config['ssid'], password=self.config['wf_pass'])
            #Устанавливаем статический IP адрес, шлюз, dns
            self.config['WIFI'].ifconfig(self.config['WIFI_AP'])
        elif self.config['MODE_WiFi'] == 'ST':
            self.config['WIFI'].active(True)
            network.phy_mode(1) # network.phy_mode = MODE_11B
            #Подключаемся к WiFi сети
            self.config['WIFI'].connect(self.config['ssid'], self.config['wf_pass'])


    #Выводим сообщения об ошибках соединения
    def _error_con(self):
        #Соединение не установлено...
        if self.config['WIFI'].status() == network.STAT_CONNECT_FAIL:
            self.dprint('WiFi: Failed due to other problems')
        #Соединение не установлено, причина не найдена точка доступа
        if self.config['WIFI'].status() == network.STAT_NO_AP_FOUND:
            self.dprint('WiFi: Failed because no access point replied')
        #Соединение не установлено, не верный пароль
        if self.config['WIFI'].status() == network.STAT_WRONG_PASSWORD:
            self.dprint('WiFi: Failed due to incorrect password')


    #Подключение к сети WiFi или поднятие точки доступа
    async def connect_wf(self):
        if self.config['MODE_WiFi'] == 'AP': #Если точка доступа
            self.dprint('WiFi AP Mode!')
            self._con() #Настройка для режима Точка доступа и подключения к сети WiFi
            if self.config['WIFI'].status() == -1:
                self.dprint('WiFi: AP Mode OK!')
                self.config['IP'] = self.config['WIFI'].ifconfig()[0]
                self.dprint('WiFi:', self.config['IP'])
                self.config['internet_outage'] = 'AP'
        elif self.config['MODE_WiFi'] == 'ST': #Если подключаемся к сети
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
                self.config['internet_outage'] = False #Сообщаем, что соединение успешно установлено
            #Если соединение по каким-то причинам не установлено
            if not self.config['WIFI'].isconnected():
                self.config['internet_outage'] = True #Сообщаем, что соединение не установлено
                self.dprint('WiFi: Connection unsuccessfully!')
            self._error_con() #Выводим сообщения, о причинах отсутствия соединения

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
            self.config['internet_outage'] = False #Сообщаем, что соединение успешно установлено
            self.dprint('WiFi: Reconnecting successfully!')
            self.dprint('WiFi:', self.config['IP'])
        self._error_con() #Выводим сообщения, о причинах отсутствия соединения
        #Если по какой-то причине соединение не установлено
        if not self.config['WIFI'].isconnected():
            self.config['internet_outage'] = True #Сообщаем, что соединение не установлено
            self.dprint('WiFi: Reconnecting unsuccessfully!')
        await asyncio.sleep(1)


class HeatControl(HeatControlBase):
    def __init__(self):
        super().__init__(config)


    #Проверка соединения с Интернетом
    async def _check_wf(self):
        while True:
            if not self.config['internet_outage']:                      #Если оединение установлено
                if self.config['WIFI'].status() == network.STAT_GOT_IP: #Проверяем наличие соединения
                    await asyncio.sleep(1)
                else:                                                   #Если соединение отсутсвует или оборвано
                    await asyncio.sleep(1)
                    self.config['internet_outage'] = True               #Сообщаем, что соединение оборвано
            else:                                                       #Если соединение отсутсвует
                await asyncio.sleep(1)
                await self.reconnect()                                  #Переподключаемся
        await asyncio.sleep(1)
        gc.collect()                                                    #Очищаем RAM


    #Подключаемся к WiFi или поднимаем точку доступа
    async def connect(self):
        await self.connect_wf()                                         #Подключение или точка доступа, зависит от настройки
        if self.config['MODE_WiFi'] == 'ST':
            loop = asyncio.get_event_loop()
            loop.create_task(self._check_wf())
        elif self.config['MODE_WiFi'] == 'AP':
            gc.collect()                                                #Очищаем RAM
    
