#!/usr/bin/python3
# coding=utf-8
import urllib.request as request
import urllib.parse as parse
import re
import os
import configparser
import time


def adif_fixup(rec):
    if "band" in rec and not "band_rx" not in rec:
        rec["band_rx"] = rec["band"]
    if "freq" in rec and "freq_rx" not in rec:
        rec["freq_rx"] = rec["freq"]


def adi_parse(adif_data):
    raw = adif_data

    # Find the EOH, in this simple example we are skipping
    # header parsing.
    pos = 0
    m = re.search("", raw, re.IGNORECASE)
    if m is not None:
        # Start parsing our ADIF file after the  marker
        pos = m.end()

    recs = []
    rec = dict()
    while 1:
        # Find our next field definition &lt;...&gt;
        pos = raw.find("<", pos)
        if pos == -1:
            return recs
        end_pos = raw.find(">", pos)

        # Split to get individual field elements out
        field_def = raw[pos + 1 : end_pos].split(":")
        field_name = field_def[0].lower()
        if field_name == "eor":
            adif_fixup(rec)  # fill in information from lookups
            recs.append(rec)  # append this record to our records list
            rec = dict()  # start a new record

            pos = end_pos
        elif len(field_def) > 1:
            # We have a field definition with a length, get it's
            # length and then assign the value to the dictionary
            field_len = int(field_def[1])
            rec[field_name] = raw[end_pos + 1 : end_pos + field_len + 1]
        pos = end_pos
    return recs

"""
MAIN 
"""
print("eQsl Downloader")
BASE_URL = "http://www.eqsl.cc"
MYCALL = ""
MYPASS = ""
MYQTH = ""
USER_HOME = os.path.expanduser("~")
APP_CONFIG_DIR = os.path.join(USER_HOME, ".eqslloader")
APP_CONFIG = os.path.join(APP_CONFIG_DIR, "config")
DATA_DIR = os.path.join(USER_HOME, "/eqsl_card")

if not os.path.isdir(APP_CONFIG_DIR):
    os.makedirs(APP_CONFIG_DIR)

print("Config folder = ", APP_CONFIG)
config = configparser.ConfigParser()
try:
    config.read(APP_CONFIG)
    MYCALL = config["GENERAL"]["MYCALL"]
    MYPASS = config["GENERAL"]["MYPASS"]
    MYQTH = config["GENERAL"]["MYQTH"]
    DATA_DIR = config["GENERAL"]["DATA_DIR"]
except Exception as e:
    print("Error", e)

if MYCALL == "" or MYPASS == "":
    print("eQSL account information.")
    MYCALL = input("Callsign : ")
    MYPASS = input("Password : ")
    MYQTH = input("Qth : ")
    DATA_DIR = input("Data Dir (e.g. /eqsl_card) : ")
    print("Save config to ", APP_CONFIG)
    config.add_section("GENERAL")
    config.set("GENERAL", "MYCALL", MYCALL)
    config.set("GENERAL", "MYPASS", MYPASS)
    config.set("GENERAL", "MYQTH", MYQTH)
    config.set("GENERAL", "DATA_DIR", DATA_DIR)
    config.write(open(APP_CONFIG, "w"))

if MYCALL == "" or MYPASS == "":
    exit()

print("Callsign = ", MYCALL)

if not os.path.isdir(DATA_DIR):
    os.makedirs(DATA_DIR)

url_opener = request.build_opener(
    request.HTTPHandler(debuglevel=0), request.HTTPCookieProcessor()
)
request.install_opener(url_opener)

print("Login")
p = parse.urlencode(
    {"Callsign": MYCALL, "EnteredPassword": MYPASS, "Login": "Go", "QTHNickname": MYQTH}
).encode("utf-8")
response = request.urlopen(BASE_URL + "/qslcard/LoginFinish.cfm", p)
data = response.read()
print("List ADI file")
data = request.urlopen(BASE_URL + "/qslcard/DownloadInBox.cfm").read().decode("utf-8")
m = re.search('<A HREF="(.*)">.ADI file</A>', data)
LOG_COUNT = 0
CARD_DOWNLOAD_COUNT = 0
if m:
    adi_file = m.group(1)
    print("Load ADI file")
    with request.urlopen(BASE_URL + "/qslcard/" + adi_file) as response:
        encoding = response.info().get_param("charset", "utf8")
        adif_data = response.read().decode(encoding, "ignore")
    logs = adi_parse(adif_data)
    for log in logs:
        LOG_COUNT += 1
        output_file = (
            DATA_DIR
            + "/"
            + log["qso_date"]
            + "-"
            + log["time_on"]
            + "-"
            + log["band"]
            + "-"
            + log["mode"]
            + "-"
            + log["call"].replace("/", "-")
            + ".png"
        )
        if not os.path.isfile(output_file):
            card_url = (
                "/qslcard/DisplayQSL.cfm?Callsign="
                + parse.quote(log["call"])
                + "&VisitorCallsign="
                + MYCALL
                + "&QSODate="
                + log["qso_date"][0:4]
                + "-"
                + log["qso_date"][4:6]
                + "-"
                + log["qso_date"][6:8]
                + "%20"
                + log["time_on"][0:2]
                + ":"
                + log["time_on"][2:4]
                + ":00.0&Band="
                + log["band"]
                + "&Mode="
                + log["mode"]
            )
            card_html = (
                request.urlopen(BASE_URL + card_url).read().decode(encoding, "ignore")
            )
            m2 = re.search(
                ' src="/CFFileServlet/_cf_image/([a-zA-Z0-9_\-.]*)"', card_html
            )
            if m2:
                card_image_url = "/CFFileServlet/_cf_image/" + m2.group(1)
                print("Load " + card_image_url + " -> " + output_file)
                image_response = request.urlopen(BASE_URL + card_image_url)
                local_file = open(output_file, "wb")
                local_file.write(image_response.read())
                local_file.close()
                CARD_DOWNLOAD_COUNT += 1
                # add delay
                time.sleep(10)
            else:
                print("Unable to find image")
else:
    print("adi file not found")

print("Log = " + str(LOG_COUNT))
print("Card download = " + str(CARD_DOWNLOAD_COUNT))
