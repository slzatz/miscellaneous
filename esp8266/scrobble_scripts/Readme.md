There are a couple of related projects in here:

1. `uscrobble2.py` and related scripts that display the sonos song that is playing on the Feather HUZZAH esp8266 using the FeatherWing OLED display.  It requires the following:
 1. `sonos_scrobble2.py` which generally runs on a raspberry pi but can run on any computer that is on same network as sonos.  It is located in repository `sonos-companion`.
 1. `echo_check_mqtt.py` which also generally runs on a raspberry pi and subscribes to an mqtt broker looking for commands like pause the music or change the volume or play certain songs.  It is located in repository `sonos-companion`.
 1. The micropython esp8266 scripts are:
    1. `font.py` - font that looks better than the default on the FeatherWing OLED
    2. `sd1306_min.py` - script I modified to write text to the OLED
    3. `uscrobble2.py`- the main script that subscribes to the song playing and can also use the buttons on the FeatherWing to increase and decrease the volume and play/pause the music.  Note for the B button to work you need to cut the trace and link GPIO16 to another pin (I used 13)
    4. `config.py` host = '54......'; ssid = '8TC'; pw = 

1. A micropython esp8266 script `volume_play_pause.py` that uses a potentiometer to change the volume and has a button to play/pause but has no display.  It also relies on `echo_check_mqtt.py` running somewhere on the same network as sonos to deal with the volume and play/pause requests.
