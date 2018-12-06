import picoweb, gc, ubinascii
from hcontroll import config
from ubinascii import hexlify
from uhashlib import sha256
gc.collect()                                                #Очищаем RAM

app = picoweb.WebApp(__name__)

http_head = """<!DOCTYPE html>
        <html>
        <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width" initial-scale="1.0" maximum-scale="1.0" minimum-scale="1.0"/>
        <title>ESP8266 ADMIN</title>
        <style> 
        html { font-family: 'Lato', Calibri, Arial, sans-serif;
               height: 100%; }
        body { background: #ddd;
            color: #333; }
        .header { width: 100%;
            padding-top: .7em;
            padding-bottom: .7em;
            float: left;
            font-size: 1.3em;
            font-weight: 400;
            text-align: center; }
        .info { margin:0 auto;
                width:200px; }
        .menu { width: 100%;
            float: left;
            font-size: 1em;
            font-weight: 400;
            text-align: center; }
        .admin { margin: 0 auto;
                 width: 350px; }
        .footer { width: 100%;
            padding-top: 2em;
            padding-bottom: 2em;
            float: left;
            font-size: .5em;
            font-weight: 400;
            text-align: center; }
        a { text-decoration: none; }
        a:link { color: #333; }
        a:visited { color: #333; }
        a:hover { color: #333; }
        a:active { color: #333; }
        a.login { font-size: 1em; }
        </style>
        </head>
        <body>
        <h2><a class="menu" href="/">HOME</a></h2> """
        
http_footer = """
        </body>
        <footer class="footer">
        &copy; 2018, <a href="https://www.facebook.com/Syslighstar" target="_blank">SYSLIGHSTAR</a>
        </footer>
        </html> """
        

def setpasswd(login:str, passwd:str) -> str:
    return str(hexlify(sha256(str(passwd+login).encode()).digest()))


@app.route("/")
def index(req, resp):
    t = config['LOCAL_TIME']
    yield from picoweb.start_response(resp)
    yield from resp.awrite(http_head)
    yield from resp.awrite("""<div class="header">
                              <a class="login" href="admin">ADMIN PANEL</a><br><br>
                              <span>MAIN PARAMETERS</span></div>""")
    yield from resp.awrite('<div class="info">')
    yield from resp.awrite('<p>Up time: %s Min</p>' %config['Uptime'])
    yield from resp.awrite('<p>Local Date: {}-{}-{}</p>'.format(t[0], t[1], t[2]))
    yield from resp.awrite('<p>Local Time: {}:{}</p>'.format(t[3], t[4]))
    yield from resp.awrite('<p>Time zone: {}</p>'.format(config['timezone']))
    yield from resp.awrite('<p>DST changes: {}</p>'.format(config['DST']))
    yield from resp.awrite('<p>IP: %s </p>' %config['IP'])
    yield from resp.awrite('<p>Avail MEM: %s Kb</p>' %config['MemAvailab'])
    yield from resp.awrite('<p>Free MEM: %s Kb</p>' %config['MemFree'])
    yield from resp.awrite('<p>Temp set: {}\'C</p>'.format(config['T_ROOM']))
    yield from resp.awrite('<p>Temp in room: {}\'C</p>'.format(config['TEMP'][1]))
    yield from resp.awrite('<p>Temp of heating: {}\'C</p>'.format(config['TEMP'][0]))
    yield from resp.awrite('<p>Power limit set: {}%</p>'.format(config['DAY_POWER']))
    yield from resp.awrite('<p>Actual power limit: {}%</p>'.format(round(config['POWER']/10)))
    yield from resp.awrite('</div>')
    yield from resp.awrite(http_footer)


@app.route("/admin")
def admin(req, resp):
    
    def new_config(data):
        print('Create new config.txt file')
        with open('config.txt', 'w') as f:
            for i in range(len(data)):
                if i != len(data)-1:
                    f.write(str(data[i])+'\n')
                else:
                    f.write(str(data[i]))
        config['T_ROOM'] = float(data[5])
        config['DAY_POWER'] = int(data[6])
                    
    def set_time(ndate, ntime, ndaylight, zone, ntp):
        config['DST'] = ndaylight
        config['timezone'] = int(zone)
        if ntp == 'True' and config['MODE_WiFi'] != 'AP':
            config['RTC'].save_time()
            config['LOCAL_TIME'] = config['RTC'].rtctime()
        else:
            dt = []
            d = ndate.split('-')
            t = ntime.split(':')
            for i in d:
                dt.append(int(i))
            for i in t:
                dt.append(int(i))
            dt.extend([0, 0, 0])
            source_time = config['SOURCE_TIME']
            config['SOURCE_TIME'] = 'web'
            config['RTC'].stime = 'web'
            config['RTC'].webtime = dt
            config['RTC'].save_time()
            config['RTC'].stime = source_time
            config['SOURCE_TIME'] = source_time
            config['LOCAL_TIME'] = config['RTC'].rtctime()
            print('Set new date: {} and new time: {}'.format(ndate, ntime))
        
    
    if req.method == "POST":
        conf = []
        with open('config.txt', 'r') as f:
            conf.insert(0, f.readline().rstrip())           #Режим работы WiFi AP или ST
            conf.insert(1, f.readline().rstrip())           #SSID для подключения к WiFi
            conf.insert(2, f.readline().rstrip())           #Пароль для подключения к WiFi
            conf.insert(3, f.readline().rstrip())           #Временная зона
            conf.insert(4, f.readline().rstrip())           #True включен переход на зимнее время False - выключен
            conf.insert(5, f.readline().rstrip())           #Температура в помещении при которой включиться отопление
            conf.insert(6, f.readline().rstrip())           #Уменьшение мощности в дневное время в %
        if b"Authorization" in req.headers:
            yield from req.read_form_data()
            try:
                wifi = req.form['wifi']
                conf[0] = req.form['wifi']
            except KeyError:
                wifi = None
            try:
                ssid = req.form['ssid']
                conf[1] = req.form['ssid']
            except KeyError:
                ssid = None
            try:
                pasw = req.form['pasw']
                conf[2] = req.form['pasw']
            except KeyError:
                pasw = None
            try:
                tzone = req.form['tzone']
                conf[3] = req.form['tzone']
            except KeyError:
                tzone = None
            try:
                daylight = req.form['daylight']
                conf[4] = req.form['daylight']
            except KeyError:
                daylight = None
            try:
                temp = req.form['temp']
                conf[5] = req.form['temp']
            except KeyError:
                temp = None
            try:
                power = req.form['power']
                conf[6] = req.form['power']
            except KeyError:
                power = None
            try:
                sdate = req.form['date']
            except KeyError:
                sdate = None
            try:
                stime = req.form['time']
            except KeyError:
                stime = None
            try:
                alogin = req.form['login']
            except KeyError:
                alogin = None
            try:
                apassw = req.form['passw']
            except KeyError:
                apassw = None
            try:
                antp = req.form['ntp']
            except KeyError:
                antp = None
            if alogin != None and apassw != None:
                if req.form['passw'] == req.form['repassw']:
                    passw = setpasswd(req.form['passw'].lower(), req.form['login'].lower())
                    with open('root.txt', 'w') as f:
                        f.write(passw)
                    with open('root.txt', 'r') as admin:
                        root = admin.readline().rstrip()    #Logim для входа в ADMIN панель
                    if root == passw:
                        yield from picoweb.start_response(resp)
                        yield from resp.awrite(http_head)
                        yield from resp.awrite("""<h3><a class="header" href="admin">ADMIN PANEL</a></h3>
                                                  <h3 class="menu">The password change is successful</h3>""")
                        yield from resp.awrite(http_footer)
                    else:
                        yield from picoweb.start_response(resp)
                        yield from resp.awrite(http_head)
                        yield from resp.awrite("""<h3><a class="header" href="admin">ADMIN PANEL</a></h3>
                                                  <h3 class="menu">Password change error</h3>""")
                        yield from resp.awrite(http_footer)
                else:
                    yield from picoweb.start_response(resp)
                    yield from resp.awrite(http_head)
                    yield from resp.awrite("""<h3><a class="header" href="admin">ADMIN PANEL</a></h3>
                                              <h3 class="menu">Passwords do not match</h3> """)
                    yield from resp.awrite(http_footer)
            elif sdate != None and stime != None and daylight != None and tzone != None:
                if conf[4] == 'True':
                    dz = 'ON'
                else:
                    dz = 'OFF'
                yield from resp.awrite(http_head)
                yield from resp.awrite('<h3><a class="header" href="admin">ADMIN PANEL</a></h3>')
                yield from resp.awrite('<div class="info">')
                if antp == 'True' and config['MODE_WiFi'] != 'AP':
                    yield from resp.awrite('<p>Time and date set from NTP server</p>')
                else:
                    yield from resp.awrite('<p>Date set: <br>{} <br>Time set: {}</p>'.format(sdate, stime))
                yield from resp.awrite('<p>Daylight time set: %s </p>' %dz)
                yield from resp.awrite('<p>Time zone set: %s </p>' %conf[3])
                yield from resp.awrite('</div>')
                yield from resp.awrite(http_footer)
                new_config(conf)
                set_time(sdate, stime, daylight, tzone, antp)
            elif wifi != None and ssid != None and pasw != None:
                yield from resp.awrite(http_head)
                yield from resp.awrite('<h3><a class="header" href="admin">ADMIN PANEL</a></h3>')
                yield from resp.awrite('<div class="info">')
                yield from resp.awrite('<p>WiFi set: %s </p>' %conf[0])
                yield from resp.awrite('<p>SSID set: %s </p>' %conf[1])
                yield from resp.awrite('<p>Password WiFi set: %s </p>' %conf[2])
                yield from resp.awrite('</div>')
                yield from resp.awrite(http_footer)
                new_config(conf)
            elif temp != None and power != None:
                yield from resp.awrite(http_head)
                yield from resp.awrite('<h3><a class="header" href="admin">ADMIN PANEL</a></h3>')
                yield from resp.awrite('<div class="info">')
                yield from resp.awrite('<p>Set temperature: %s </p>' %conf[5])
                yield from resp.awrite('<p>Power limit set: %s </p>' %conf[6])
                yield from resp.awrite('</div>')
                yield from resp.awrite(http_footer)
                new_config(conf)
    else:
        if b"Authorization" not in req.headers:
            yield from resp.awrite('HTTP/1.0 401 NA\r\n'
               'WWW-Authenticate: Basic realm="Picoweb Realm"\r\n'
                '\r\n')
            return
        auth = req.headers[b"Authorization"].split(None, 1)[1]
        auth = ubinascii.a2b_base64(auth).decode()
        username, passwd = auth.split(":", 1)
        with open('root.txt') as admin:
            root = admin.readline().rstrip()    #Logim для входа в ADMIN панель
        if setpasswd(passwd.lower(), username.lower()) == root:
            yield from picoweb.start_response(resp)
            yield from resp.awrite(http_head)
            yield from resp.awrite("""
            <div class="header"><span>ESP8266 Admin</span></div>
            <br>
            <div class = "admin">
            <form action='admin' method='POST'>
                <fieldset>
                    <legend>Setting date and time</legend>
                    <p><input type="radio" name="daylight" checked value="True">Daylight time ON<br>
                       <input type="radio" name="daylight" value="False">Daylight time OFF</p>
                    <p><input type="checkbox" name="ntp" checked value="True">Time from NTP server</p>
                    <p><select size="1" name="tzone" required>
                       <option value="0">UTC 00:00</option>
                       <option value="1">UTC +01:00</option>
                       <option value="2">UTC +02:00</option>
                       <option value="3">UTC +03:00</option>
                       <option value="4">UTC +04:00</option>
                       <option value="5">UTC +05:00</option>
                       <option value="6">UTC +06:00</option>
                       </select></p>
                    <fieldset>
                        <legend>Setting time without an NTP server</legend>
                        <p><input type="date" name="date" required></p>
                        <p><input type="time" name="time" required></p>
                    </fieldset>
                    <p><input type="submit" value="Set Date&Time"></p>
                </fieldset>
            </form>
            <br>
            <form action='admin' method='POST'>
                <fieldset>
                    <legend>Setting WiFi</legend>
                    <p><input type="radio" name="wifi" value="AP">AP<br>
                       <input type="radio" name="wifi" value="ST" checked>STATION</p>
                    <p><input type="text" name="ssid" placeholder="SSID" required autocomplete="off"></p>
                    <p><input type="password" name="pasw" pattern=".{8,12}" required title="8 to 12 characters" placeholder="WiFi Password" required autocomplete="off"></p>
                    <p><input type="submit" value="Set WiFi"></p>
                </fieldset>
            </form>
            <br>
            <form action='admin' method='POST'>
                <fieldset>
                    <legend>Power and temperature setting</legend>
                    <p><input type="number" name="temp" size="4" min="18.0" max="25.0" step="0.1" value="21.0">'C<br>Temperature</p>
                    <p><input type="number" name="power" size="4" min="0" max="100" step="5" value="50">%<br>Daytime power limit</p>
                    <p><input type="submit" value="Set Temp&Power"></p>
                </fieldset>
            </form>
            <br>
            <form action='admin' method='POST'>
                <fieldset>
                    <legend>Chenge password</legend>
                    <p><input type="text" name="login" required placeholder="Login" autocomplete="off"></p>
                    <p><input type="password" name="passw" pattern=".{4,8}" required title="8 to 12 characters" required placeholder="Password" autocomplete="off"></p>
                    <p><input type="password" name="repassw" pattern=".{4,8}" required title="8 to 12 characters" required placeholder="Repeat Password" autocomplete="off"></p>
                    <p><input type="submit" value="Сhange password"></p>
                </fieldset>
            </form>
            </div>""")
            yield from resp.awrite(http_footer)
        else:
            yield from picoweb.start_response(resp)
            yield from resp.awrite(http_head)
            yield from resp.awrite("""<div class="header"><span>Error Login</span></div>""")
            yield from resp.awrite(http_footer)
