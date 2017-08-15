#!/usr/bin/python2
import RPi.GPIO as GPIO
import time
import bugsnag
import sys
from pushbullet import PushBullet
import ConfigParser
import os

bg_api = ""
pb_api = ""
pin_sensor = 4
debug = False


def debug_print(msg):
    """Prints the provided message if -debug was passed as an argument"""
    if debug:
        print(msg)


def pb_alert(title, msg):
    """Makes a Pushbullet push using the configured API key and provided title and message"""
    pb = PushBullet(pb_api)
    pb.push_note(title, msg)


def setup_gpio():
    """Setups GPIO on the configured pin"""
    debug_print("Setting up GPIO on GPIO{}".format(pin_sensor))
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin_sensor, GPIO.IN)


def setup_bugsnag():
    """Setups Bugsnag using the configured API key"""
    debug_print("Setting up Bugsnag")

    global bg_api
    bugsnag.configure(
        api_key=bg_api
    )


def setup():
    """Calls other setup methods and reads configuration file"""
    if len(sys.argv) > 1:
        global debug
        debug = (sys.argv[1] == "-debug")
        debug_print("Debugging")
    setup_gpio()
    setup_bugsnag()

    cp = ConfigParser.RawConfigParser()
    config = os.path.join(os.path.dirname(os.path.realpath(__file__)), "appliancealert.ini")
    cp.read(config)

    global bg_api
    global pb_api
    bg_api = cp.get('appliance-alert', 'bugsnag_api')
    pb_api = cp.get('appliance-alert', 'pb_api')


def determine_if_in_cycle(watch_time=60):
    """Reads from the configured GPIO pin for the specified watch_time"""
    stats = {
        'on': 0,
        'off': 0
    }
    start_time = time.time()
    mon_time = 0
    debug_print("Watching for {} seconds...".format(watch_time))
    while mon_time < watch_time:
        is_vib = GPIO.input(4)  # 0 = not vib, 1 = vib
        if is_vib:
            stats['on'] += 1
        else:
            stats['off'] += 1

        mon_time = time.time() - start_time
        time.sleep(.01)

    on_hits = stats['on']
    off_hits = stats['off']
    total_checks = float(stats['on'] + stats['off'])  # make this a float so the percentage comes out right

    debug_print("")
    debug_print("=== STATS ===")
    debug_print("Checks: {}".format(total_checks))
    debug_print("On for {} checks".format(on_hits))
    debug_print("Off for {} checks".format(off_hits))
    debug_print("Vibrated {0:.2f}% of the time".format((on_hits / total_checks) * 100))
    debug_print("")

    return ((on_hits / total_checks) * 100) > 5


def main():
    try:
        setup()
        last_vibr = 0
        in_cycle = False
        while True:
            print("In cycle: {}".format(in_cycle))
            if in_cycle:
                temp_in_cycle = determine_if_in_cycle(5)
                if temp_in_cycle:
                    last_vibr = time.time()
                else:
                    debug_print("No activity detected for {}".format(time.time() - last_vibr))
                    debug_print("")
                    if (
                        time.time() - last_vibr) > 300:  # wait 5 minutes before declaring out of cycle to prevent false alerts (drain cycles)
                        in_cycle = False

                if not in_cycle:
                    pb_alert("Washer", "The washer has completed its cycle!")
            else:
                in_cycle = determine_if_in_cycle(5)
                if in_cycle:
                    pb_alert("Washer", "We are now in a cycle!")
                    debug_print("We are now in a cycle...")

    except KeyboardInterrupt:
        debug_print("Control + C!")
        exit(code=0)
    except Exception as e:
        debug_print("Unhandled exception!")
        debug_print(e)
        bugsnag.notify(e)
        exit(code=1)


main()