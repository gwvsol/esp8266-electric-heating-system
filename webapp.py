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
        <title>Heating System</title>
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
        
href_adm_panel = '<a class="login" href="admin">ADMIN PANEL</a>'
div_cl_header = '<div class="header">'
div_cl_info = '<div class="info">'
div_cl_admin = '<div class = "admin">'
div_end = '</div>'
span_err_pasw = '<span>Error Login<br>Close the browser, restart it,<br>and then try to log in again</span>'
mode_temp_power = """<form action='admin' method='POST'>
                <fieldset>
                    <legend>Set Mode, Power, temperature and time work</legend>
                    <p><input type="number" name="temp" size="4" min="18.0" max="25.0" step="0.1" value="20.0">'C<br>Temperature</p>
                    <p><input type="number" name="power" size="4" min="10" max="80" step="5" value="50">%<br>Daytime power limit</p>
                    <p><input type="radio" name="work_mode" value="contin">Continuous work<br>
                        <input type="radio" name="work_mode" value="schedule">On schedule<br>
                        <input type="radio" name="work_mode" value="offall">Turn off heating boiler</p>
                    <p>Time<br>
                        <input type="time" name="time_on" required>On<br></p>
                        <p><input type="time" name="time_off" required>Off<br></p>
                    <p><input type="submit" value="Set control"></p>
                </fieldset>
            </form>"""
date_set = """<form action='admin' method='POST'>
                <fieldset>
                    <legend>Setting date and time</legend>
                    <p>Daylight saving time<br>
                       <input type="radio" name="daylight" checked value="True">ON<br>
                       <input type="radio" name="daylight" value="False">OFF</p>
                    <p>Time on NTP server<br>
                        <input type="radio" name="ntp" checked value="True">ON<br>
                        <input type="radio" name="ntp" value="False">OFF</p>
                    <p><select size="1" name="tzone" required>
                       <option value="0">UTC +00:00</option>
                       <option value="1">UTC +01:00</option>
                       <option value="2">UTC +02:00</option>
                       <option value="3">UTC +03:00</option>
                       <option value="4">UTC +04:00</option>
                       </select></p>
                    <fieldset>
                        <legend>Setting time without an NTP server</legend>
                        <p><input type="date" name="date" required></p>
                        <p><input type="time" name="time" required></p>
                    </fieldset>
                    <p><input type="submit" value="Set Date&Time"></p>
                </fieldset>
            </form>"""
wifi_form = """<form action='admin' method='POST'>
                    <fieldset>
                        <legend>Setting WiFi</legend>
                        <p><input type="radio" name="wifi" value="AP">AP<br>
                           <input type="radio" name="wifi" value="ST" checked>STATION</p>
                        <p><input type="text" name="ssid" placeholder="SSID" required autocomplete="off"></p>
                        <p><input type="password" name="pasw" pattern=".{8,12}" required title="8 to 12 characters" placeholder="WiFi Password" required autocomplete="off"></p>
                        <p><input type="submit" value="Set WiFi"></p>
                    </fieldset>
               </form>"""
passw_form = """<form action='admin' method='POST'>
                    <fieldset>
                        <legend>Chenge password</legend>
                        <p><input type="text" name="login" required placeholder="Login" autocomplete="off"></p>
                        <p><input type="password" name="passw" pattern=".{8,12}" required title="8 to 12 characters" required placeholder="Password" autocomplete="off"></p>
                        <p><input type="password" name="repassw" pattern=".{8,12}" required title="8 to 12 characters" required placeholder="Repeat Password" autocomplete="off"></p>
                        <p><input type="submit" value="Сhange password"></p>
                    </fieldset>
                </form>"""
http_footer = """</body>
                <footer class="footer">
                    &copy; 2019, <a href="https://www.facebook.com/Syslighstar" target="_blank">SYSLIGHSTAR</a>
                </footer>
            </html>"""


def bool_to_str(s):
    if s == True:
        return 'ON'
    elif s == False:
        return 'OFF'

@app.route("/")
def index(req, resp):
    t = config['RTC_TIME']
    yield from picoweb.start_response(resp)
    yield from resp.awrite(http_head)
    yield from resp.awrite('{}{}<br>{}'\
                .format(div_cl_header, href_adm_panel, div_end))
    yield from resp.awrite(div_cl_info)
    yield from resp.awrite('<p>{:0>2d}-{:0>2d}-{:0>2d} {:0>2d}:{:0>2d}</p>'.format(t[0], t[1], t[2], t[3], t[4]))
    yield from resp.awrite('<p>Time zone: {}</p>'.format(config['timezone']))
    yield from resp.awrite('<p>DST: {}</p>'.format(bool_to_str(config['DST'])))
    yield from resp.awrite('<p>Heating: {}</p>'.format(bool_to_str(config['HEAT'])))
    yield from resp.awrite('<p>Set: {:.1f}\'C</p>'.format(config['T_ROOM']))
    yield from resp.awrite('<p>Room: {:.1f}\'C</p>'.format(config['TEMP']))
    yield from resp.awrite('<p>Power set: {}%</p>'.format(config['WEBPOWER']))
    yield from resp.awrite('<p>Actual power: {}%</p>'.format(round(config['POWER']/10)))
    yield from resp.awrite(div_end)
    yield from resp.awrite(http_footer)
