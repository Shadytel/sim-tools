#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" toorsimtool.py: A toolkit for the Toorcamp SIM cards

	Requires the pySim libraries (http://cgit.osmocom.org/cgit/pysim/)
"""

#
# Copyright (C) 2012  Karl Koscher <supersat@cs.washington.edu>
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

from pySim.commands import SimCardCommands
from pySim.utils import swap_nibbles
try:
	import argparse
except Exception, err:
	print "Missing argparse -- try apt-get install python-argparse"
import zipfile
import time
import struct

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

class AppLoaderCommands(object):
	def __init__(self, transport):
		self._tp = transport
		self._apduCounter = 0;

	def send_terminal_profile(self):
		return self._tp.send_apdu_checksw('A010000011FFFF000000000000000000000000000000')

	# Wrap an APDU inside an SMS-PP APDU	
	def send_wrapped_apdu(self, data):
		# Command packet header
		# SPI: PoR required
		# TAR: Remote App Management (000000)
		envelopeData = '0D0001000000000000000000' + ('%02x' % (self._apduCounter & 0xff)) + '00' + data;
		self._apduCounter = self._apduCounter + 1

		# Command
		envelopeData = '027000' + ('%04x' % (len(envelopeData) / 2)) + envelopeData;

		# SMS-TDPU header: MS-Delivery, no more messages, TP-UD header, no reply path,
		# TP-OA = TON/NPI 55667788, TP-PID = SIM Download, BS timestamp
		envelopeData = '400881556677887ff600112912000004' + ('%02x' % (len(envelopeData) / 2)) + envelopeData;

		# (82) Device Identities: (83) Network to (81) USIM
		# (8b) SMS-TPDU 
		envelopeData = '820283818B' + hex_ber_length(envelopeData) + envelopeData
		
		# d1 = SMS-PP Download, d2 = Cell Broadcast Download
		envelopeData = 'd1' + hex_ber_length(envelopeData) + envelopeData;
		response = self._tp.send_apdu_checksw('a0c20000' + ('%02x' % (len(envelopeData) / 2)) + envelopeData)[0]

		# Unwrap response
		response = response[(int(response[10:12],16)*2)+12:]
		return (response[6:], response[2:6])

	def send_wrapped_apdu_checksw(self, data, sw="9000"):
		response = self.send_wrapped_apdu(data)
		if response[1] != sw:
			raise RuntimeError("SW match failed! Expected %s and got %s." % (sw.lower(), response[1]))
		return response

	def get_security_domain_aid(self):
		# Get Status followed by Get Response
		response = self.send_wrapped_apdu_checksw('80F28000024F0000C0000000')[0]
		return response[2:(int(response[0:2],16)*2)+2]

	def delete_aid(self, aid, delete_related=True):
		aidDesc = '4f' + ('%02x' % (len(aid) / 2)) + aid
		apdu = '80e400' + ('80' if delete_related else '00') + ('%02x' % (len(aidDesc) / 2)) + aidDesc + '00c0000000'
		return self.send_wrapped_apdu(apdu)

	def load_aid_raw(self, aid, executable, codeSize, volatileDataSize = 0, nonvolatileDataSize = 0):
		loadParameters = 'c602' + ('%04x' % codeSize)
		if volatileDataSize > 0:
			loadParameters = loadParameters + 'c702' ('%04x' % volatileDataSize)
		if nonvolatileDataSize > 0:
			loadParameters = loadParameters + 'c802' ('%04x' % nonvolatileDataSize)
		loadParameters = 'ef' + ('%02x' % (len(loadParameters) / 2)) + loadParameters
		
		# Install for load APDU, no security domain or hash specified
		data = ('%02x' % (len(aid) / 2)) + aid + '0000' + ('%02x' % (len(loadParameters) / 2)) + loadParameters + '0000'
		self.send_wrapped_apdu_checksw('80e60200' + ('%02x' % (len(data) / 2)) + data + '00c0000000')

		# Load APDUs
		loadData = 'c4' + hex_ber_length(executable) + executable
		loadBlock = 0;

		while len(loadData):
			if len(loadData) > 0xd8:
				apdu = '80e800' + ('%02x' % loadBlock) + '6c' + loadData[:0xd8]
				loadData = loadData[0xd8:]
				loadBlock = loadBlock + 1
			else:
				apdu = '80e880' + ('%02x' % loadBlock) + ('%02x' % (len(loadData) / 2)) + loadData
				loadData = ''

			self.send_wrapped_apdu_checksw(apdu + '00c0000000')
	
	def generate_load_file(self, capfile):
		zipcap = zipfile.ZipFile(capfile)
		zipfiles = zipcap.namelist()

		header = None
		directory = None
		impt = None
		applet = None
		clas = None
		method = None
		staticfield = None
		export = None
		constpool = None
		reflocation = None

		for i, filename in enumerate(zipfiles):
			if filename.lower().endswith('header.cap'):
				header = zipcap.read(filename)
			elif filename.lower().endswith('directory.cap'):
				directory = zipcap.read(filename)
			elif filename.lower().endswith('import.cap'):
				impt = zipcap.read(filename)
			elif filename.lower().endswith('applet.cap'):
				applet = zipcap.read(filename)
			elif filename.lower().endswith('class.cap'):
				clas = zipcap.read(filename)
			elif filename.lower().endswith('method.cap'):
				method = zipcap.read(filename)
			elif filename.lower().endswith('staticfield.cap'):
				staticfield = zipcap.read(filename)
			elif filename.lower().endswith('export.cap'):
				export = zipcap.read(filename)
			elif filename.lower().endswith('constantpool.cap'):
				constpool = zipcap.read(filename)
			elif filename.lower().endswith('reflocation.cap'):
				reflocation = zipcap.read(filename)

		data = header.encode("hex")
		if directory:
			data = data + directory.encode("hex")
		if impt:
			data = data + impt.encode("hex")
		if applet:
			data = data + applet.encode("hex")
		if clas:
			data = data + clas.encode("hex")
		if method:
			data = data + method.encode("hex")
		if staticfield:
			data = data + staticfield.encode("hex")
		if export:
			data = data + export.encode("hex")
		if constpool:
			data = data + constpool.encode("hex")
		if reflocation:
			data = data + reflocation.encode("hex")

		return data

	def get_aid_from_load_file(self, data):
		return data[26:26+(int(data[24:26],16)*2)]
		 
	def load_app(self, capfile):
		data = self.generate_load_file(capfile)
		aid = self.get_aid_from_load_file(data)
		self.load_aid_raw(aid, data, len(data) / 2)

	def install_app(self, args):
		loadfile = self.generate_load_file(args.install)
		aid = self.get_aid_from_load_file(loadfile)

		toolkit_params = ''
		if args.enable_sim_toolkit:
			assert len(args.access_domain) % 2 == 0
			assert len(args.priority_level) == 2
			toolkit_params = ('%02x' % (len(args.access_domain) / 2))  + args.access_domain
			toolkit_params = toolkit_params + args.priority_level + ('%02x' % args.max_timers)
			toolkit_params = toolkit_params + ('%02x' % args.max_menu_entry_text)
			toolkit_params = toolkit_params + ('%02x' % args.max_menu_entries) + '0000' * args.max_menu_entries + '0000'
			toolkit_params = 'ca' + ('%02x' % (len(toolkit_params) / 2)) + toolkit_params

		assert len(args.nonvolatile_memory_required) == 4
		assert len(args.volatile_memory_for_install) == 4
		parameters = 'c802' + args.nonvolatile_memory_required + 'c702' + args.volatile_memory_for_install
		if toolkit_params:
			parameters = parameters + toolkit_params
		parameters = 'ef' + ('%02x' % (len(parameters) / 2)) + parameters + 'c9' + ('%02x' % (len(args.app_parameters) / 2)) + args.app_parameters
		
		data = ('%02x' % (len(aid) / 2)) + aid + ('%02x' % (len(args.module_aid) / 2)) + args.module_aid + ('%02x' % (len(args.instance_aid) / 2)) + \
			   args.instance_aid + '0100' + ('%02x' % (len(parameters) / 2)) + parameters + '00'
		self.send_wrapped_apdu_checksw('80e60c00' + ('%02x' % (len(data) / 2)) + data + '00c0000000')
#------

parser = argparse.ArgumentParser(description='Tool for Toorcamp SIMs.')
parser.add_argument('-s', '--serialport')
parser.add_argument('-p', '--pcsc', nargs='?', const=0, type=int)
parser.add_argument('-d', '--delete-app')
parser.add_argument('-l', '--load-app')
parser.add_argument('-i', '--install')
parser.add_argument('--module-aid')
parser.add_argument('--instance-aid')
parser.add_argument('--nonvolatile-memory-required', default='0000')
parser.add_argument('--volatile-memory-for-install', default='0000')
parser.add_argument('--enable-sim-toolkit', action='store_true')
parser.add_argument('--access-domain', default='ff')
parser.add_argument('--priority-level', default='01')
parser.add_argument('--max-timers', type=int, default=0)
parser.add_argument('--max-menu-entry-text', type=int, default=16)
parser.add_argument('--max-menu-entries', type=int, default=0)
parser.add_argument('--app-parameters', default='')
parser.add_argument('--print-info', action='store_true')
parser.add_argument('-n', '--new-card-required', action='store_true')
parser.add_argument('-z', '--sleep_after_insertion', type=float, default=0.0)
parser.add_argument('--disable-pin')
parser.add_argument('-t', '--list-applets', action='store_true')

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
ac = AppLoaderCommands(sl)

sl.wait_for_card(newcardonly=args.new_card_required)
time.sleep(args.sleep_after_insertion)

# Get the ICCID
print "ICCID: " + swap_nibbles(sc.read_binary(['3f00', '2fe2'])[0])
ac.send_terminal_profile()

if args.delete_app:
	ac.delete_aid(args.delete_app)

if args.load_app:
	ac.load_app(args.load_app)

if args.install:
	ac.install_app(args)

if args.print_info:
	print "--print-info not implemented yet."

if args.disable_pin:
	sl.send_apdu_checksw('0026000108' + args.disable_pin.encode("hex") + 'ff' * (8 - len(args.disable_pin)))

if args.list_applets:
	(data, status) = ac.send_wrapped_apdu('80f21000024f0000c0000000')
	while status == '6310':
		(partData, status) = ac.send_wrapped_apdu('80f21001024f0000c0000000')
		data = data + partData

	while len(data) > 0:
		aidlen = int(data[0:2],16) * 2
		aid = data[2:aidlen + 2]
		state = data[aidlen + 2:aidlen + 4]
		privs = data[aidlen + 4:aidlen + 6]
		num_instances = int(data[aidlen + 6:aidlen + 8], 16)
		print 'AID: ' + aid + ', State: ' + state + ', Privs: ' + privs
		data = data[aidlen + 8:]
		while num_instances > 0:
			aidlen = int(data[0:2],16) * 2
			aid = data[2:aidlen + 2]
			print "\tInstance AID: " + aid
			data = data[aidlen + 2:]
			num_instances = num_instances - 1
