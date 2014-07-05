#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" simprep-2014.py: A tool for the Toorcamp SIM cards in 2014

	Requires the pySim libraries (http://cgit.osmocom.org/cgit/pysim/)
"""

#
# Copyright (C) 2012  Karl Koscher <supersat@cs.washington.edu>
# Portions copyright (C) 2014 Astrid Smith <Astrid@xrtc.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# I think the only thing holding us back from python3 is:
# ImportError: No module named 'smartcard'
# ?

from pySim.commands import SimCardCommands
from pySim.utils import swap_nibbles, rpad, b2h
import argparse
import zipfile
import time
import struct
import sqlite3

#------

def hex_ber_length(data):
        dataLen = len(data) / 2
        if dataLen < 0x80:
                return '%02x' % dataLen
                dataLen = '%x' % dataLen
                lenDataLen = len(dataLen)
                if lenDataLen % 2:
                        dataLen = '0' + dataLen
                        lenDataLen = lenDataLen + 1
                        return ('%02x' % (0x80 + (lenDataLen / 2))) + dataLen

def clear_phonebook():
        

def set_phonebook(slot, name, number, capability='ff'):
        num_records = sc.record_count(['3f00','7f10','6f3a'])
        record_size = sc.record_size(['3f00','7f10','6f3a'])
        record_num = int(slot)
        if (record_num < 1) or (record_num > num_records):
                raise RuntimeError("Invalid phonebook record number")
                encoded_name = rpad(b2h(name), (record_size - 14) * 2)
                if len(encoded_name) > ((record_size - 14) * 2):
                        raise RuntimeError("Name is too long")
                        if len(number) > 20:
                                raise RuntimeError("Number is too long")
                                encoded_number = swap_nibbles(rpad(args.set_phonebook_entry[2], 20))
                                record = encoded_name + ('%02x' % len(number)) + capability + encoded_number + 'ffff'
                                sc.update_record(['3f00','7f10','6f3a'], record_num, record)

def get_imsi():
        imsi_raw = (sc.read_binary(['3f00', '7f20', '6f07'])[0])
        imsi_len = imsi_raw[1]
        imsi = swap_nibbles(imsi_raw[2:])[1:]
        print ("IMSI: %s" % imsi)
        return imsi

def get_next_extension(db):
        cur = db.cursor()
        last_extn = cur.execute("select extension from subscriber where extension like '22____' order by extension desc limit 1;").fetchone()[0]
        return "%06d" % (int(last_extn) + 1)



parser = argparse.ArgumentParser(description='Tool for Toorcamp 2014 SIMs.')
parser.add_argument('-s', '--serialport')
parser.add_argument('-p', '--pcsc', nargs='?', const=0, type=int)
parser.add_argument('-i', '--install')
parser.add_argument('--print-info', action='store_true')
parser.add_argument('-n', '--new-card-required', action='store_true')
parser.add_argument('-z', '--sleep_after_insertion', type=float, default=0.0)
parser.add_argument('--disable-pin')
parser.add_argument('--pin')
parser.add_argument('--tar')
parser.add_argument('--dump-phonebook', action='store_true')
parser.add_argument('--set-phonebook-entry', nargs=4)

parser.add_argument('--record', action="store_true")
parser.add_argument('--print')
parser.add_argument('--sqlite-db', nargs=1)

args = parser.parse_args()

if args.pcsc is not None:
        from pySim.transport.pcsc import PcscSimLink
        sl = PcscSimLink(args.pcsc)
elif args.serialport is not None:
        from pySim.transport.serial import SerialSimLink
        sl = SerialSimLink(device=args.serialport, baudrate=9600)
else:
        raise RuntimeError("Need to specify either --serialport or --pcsc")

sc = SimCardCommands(sl)

sl.wait_for_card(newcardonly=args.new_card_required)
time.sleep(args.sleep_after_insertion)

# Get the ICCID
print("ICCID: %s" % swap_nibbles(sc.read_binary(['3f00', '2fe2'])[0]))

if args.pin:
        sc.verify_chv(1, args.pin)

if args.print_info:
        print("--print-info not implemented yet.")

if args.disable_pin:
        sl.send_apdu_checksw('0026000108' + args.disable_pin.encode("hex") + 'ff' * (8 - len(args.disable_pin)))

if args.dump_phonebook:
        num_records = sc.record_count(['3f00','7f10','6f3a'])
        print("Phonebook: %d records available" % num_records)
        for record_id in range(1, num_records + 1):
                print(sc.read_record(['3f00','7f10','6f3a'], record_id))

if args.sqlite_db:
        dbh = sqlite3.connect(args.sqlite_db[0])

if args.set_phonebook_entry:
        set_phonebook(args.set_phonebook_entry[0],
                      args.set_phonebook_entry[1],
                      args.set_phonebook_entry[2],
                      args.set_phonebook_entry[3])

# This is a SIM card to put into the HLR.
"""
CREATE TABLE Subscriber (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	created TIMESTAMP NOT NULL,
	updated TIMESTAMP NOT NULL,
	imsi NUMERIC UNIQUE NOT NULL,
	name TEXT,
	extension TEXT UNIQUE,
	authorized INTEGER NOT NULL DEFAULT 0,
	tmsi TEXT UNIQUE,
	lac INTEGER NOT NULL DEFAULT 0,
	expire_lu TIMESTAMP DEFAULT NULL
);
"""
#
if args.record:
        imsi = get_imsi()
        set_phonebook(1, "Shadytel Service", "3000")
        set_phonebook(2, "Camp Registration", "3001")
        set_phonebook(3, "Camp Administration", "3002")
        set_phonebook(4, "Tone test", "720")
        set_phonebook(5, "Echo test", "722")

        extn = get_next_extension(dbh)
        print("Extension: %s" % extn)

        dbh.cursor().execute("insert into subscriber (imsi, extension, authorized, created, updated) values (?, ?, 1, datetime('now'), datetime('now') );", (imsi, extn))
        dbh.commit()

