#!/usr/bin/env python
#-*- coding: UTF-8 -*-

import time
import datetime
import os 
import logging, logging.handlers
import socket, select, string, sys
import MySQLdb as mdb
import calendar
import threading  
import math
import osr

########################################################################
from configobj import ConfigObj
config = ConfigObj("./indoor.conf")

rf1_host = config['RF1_IP']
rf1_port = config['RF1_PORT']
rf2_host = config['RF2_IP']
rf2_port = config['RF2_PORT']
rf3_host = config['RF3_IP']
rf3_port = config['RF3_PORT']
rf4_host = config['RF4_IP']
rf4_port = config['RF4_PORT']
rf_lat = [0,config['RF1_LAT'],config['RF2_LAT'],config['RF3_LAT'],config['RF4_LAT']]
rf_lon = [0,config['RF1_LON'],config['RF2_LON'],config['RF3_LON'],config['RF4_LON']]
kcs_host = config['KCS_HOST']


########################################################################
LOG = "./indoor.log"
LOG_FOR_ROTATE = 30

conDB = None
socketKCS = None

data_strength  = [0] * 100
########################################################################


########################################################################
# definicion y configuracion de logs
try:
    logger = logging.getLogger('indoor')
    loggerHandler = logging.handlers.TimedRotatingFileHandler(LOG , 'midnight', 1, backupCount=LOG_FOR_ROTATE)
    formatter = logging.Formatter('%(message)s')
    loggerHandler.setFormatter(formatter)
    logger.addHandler(loggerHandler)
    logger.setLevel(logging.DEBUG)
except Exception, error:
    print '------------------------------------------------------------------'
    print '[ERROR] Error writing log at %s' % error
    print '------------------------------------------------------------------'
    exit()
########################################################################

class TagThread(threading.Thread):  
	def __init__(self, num):  
		threading.Thread.__init__(self)  
		self.num = num  
	def run(self):  
		print "Hilo para el Tag", self.num
		#while 1:
			#print "Hilo para el Tag", self.num
			#time.sleep(1)

def test():
	logger.info ("START TEST")
	
	#connect_database()
	#cur = conDB.cursor()
	tag_id = '01'
	payload = 760
	actual_date = 212
	power = 68
	#cur.execute("INSERT INTO TAG_DATA (TAG_ID, PAYLOAD, DATA_DATE, POWER) VALUES (%s, %d, %d, %d)", (tag_id, int(payload), int(actual_date), int(power)))
	#print unix_time(time.localtime())
	print calendar.timegm(time.gmtime())

def transform_utm_to_wgs84(easting, northing, zone):
    utm_coordinate_system = osr.SpatialReference()
    utm_coordinate_system.SetWellKnownGeogCS("WGS84") # Set geographic coordinate system to handle lat/lon
    is_northern = northing > 0    
    utm_coordinate_system.SetUTM(zone, is_northern)

    wgs84_coordinate_system = utm_coordinate_system.CloneGeogCS() # Clone ONLY the geographic coordinate system 

    # create transform component
    utm_to_wgs84_transform = osr.CoordinateTransformation(utm_coordinate_system, wgs84_coordinate_system) # (<from>, <to>)
    return utm_to_wgs84_transform.TransformPoint(easting, northing, 0) # returns lon, lat, altitude

def connect_kcs():
	global socketKCS
	socketKCS = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	socketKCS.settimeout(0.05)
	server_host_KCS = config['KCS_HOST']
	server_port_KCS = int(config['KCS_PORT'])
	try:
		socketKCS.connect((server_host_KCS, server_port_KCS))
		logger.info('Successfully connected to KCS')
	except Exception, error:
		logger.error('Error connecting to KCS: %s', error)

def sendDataKCS(data,TOTAL):
	global socketKCS
	server_host_KCS = config['KCS_HOST']
	server_port_KCS = int(config['KCS_PORT'])
	try:
		socketKCS.send(data)
		logger.info("[KCS][%d] %s", TOTAL, data[0:len(data)-2])
	except Exception, error:
		logger.error('Error sending data to KCS: %s',error)
		logger.info('Trying reconnection to KCS')
		try:
			socketKCS.connect((server_host_KCS, server_port_FIA1))
			socketKCS.send(data)
		except:
			logger.info('Failed reconnection to KCS')

def connect_database():
	global conDB
	db_ip = config['DB_IP']
	db_port = config['DB_PORT']
	db_name = config['DB_NAME']
	db_user = config['DB_USER']
	db_passwd = config['DB_PASSWD']
	try:
		#con = mdb.connect(host=db_ip, port=int(db_port), user=db_user, passwd=db_passwd, db=db_name)
		conDB = mdb.connect(db_ip, db_user, db_passwd, db_name)
		logger.debug ('Conectado a Base de Datos')
	except mdb.Error, e:
		logger.error ("Error de conexion a BBDD %d: %s" % (e.args[0], e.args[1]))

def disconnect_database():
	global conDB
	if conDB:
		conDB.close()

def process_data(reader_id,data):
	global rf_lat
	global rf_lon
	global data_strength
	global socketKCS
	for msg in data:
		try:
			if (len(str(msg)))>0:
				v_msg = msg.split(",")
				#if (v_msg[0]=='H' and len(v_msg)==5):
				if (v_msg[0]=='H'):
					tag_id = v_msg[1]
					payload = v_msg[3]
					reader_id = int(reader_id)
					payload = payload[1:len(payload)]
					strength = v_msg[5]
					strength = int(strength[1:len(strength)])
					milisegundos = calendar.timegm(time.gmtime())
					cur = conDB.cursor()
					query = "INSERT INTO TAG_DATA (TAG_ID, READER_ID, PAYLOAD, DATA_DATE, STRENGTH) VALUES ('"+tag_id+"',"+str(reader_id)+","+str(payload)+","+str(milisegundos)+","+str(strength)+")"
					#print query
					#cur.execute(query)
					#data[int(tag_id)][int(reader_id)] = strength
					if (tag_id == '00050944'):
						#print str(reader_id) + " - " + str(strength)
						data_strength[reader_id] = strength
						sum_strength = data_strength[1]+data_strength[2]+data_strength[3]+data_strength[4]
						lat = (float(rf_lat[1])*data_strength[1] + float(rf_lat[2])*data_strength[2] + float(rf_lat[3])*data_strength[3] + float(rf_lat[4])*data_strength[4])/sum_strength
						lon = (float(rf_lon[1])*data_strength[1] + float(rf_lon[2])*data_strength[2] + float(rf_lon[3])*data_strength[3] + float(rf_lon[4])*data_strength[4])/sum_strength
						#print ("-->"+str(lat)+","+str(lon))
						coordenadas = transform_utm_to_wgs84(lat,lon,30)
						print str(coordenadas[1]) + "," + str(coordenadas[0])
						trama = str(tag_id) +","+str(milisegundos)+","+str(lon)+","+str(lat)+",20,246,14,9,2,0.0,0.9,3836"+'\r\n'
						socketKCS.sendall(trama)
						#print sum_strength
		except Exception,e:
			print e 
			pass
		
def main():
	hora_actual = time.strftime("20%y/%m/%d %H:%M:%S", time.localtime())
	logger.info ("START - "+hora_actual)

	#t = TagThread(1)  
	#t.start()  
	#t.join()

	connect_database()
	connect_kcs()

	s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s1.settimeout(2)
	s2.settimeout(2)
	s3.settimeout(2)
	s4.settimeout(2)

    # connect to RF Readers
	if (config['RF1_ENABLE'] == "true"):
		try :
			s1.connect((rf1_host, int(rf1_port)))
			logger.info ('Conectado al lector RF1')
		except Exception, errorMsg:
			logger.error ('Error de conexion al lector RF1: '+rf1_host+":"+rf1_port)
			logger.error (errorMsg)     

	if (config['RF2_ENABLE'] == "true"):
		try :
			s2.connect((rf2_host, int(rf2_port)))
			logger.info ('Conectado al lector RF2')
		except Exception, errorMsg:
			logger.error ('Error de conexion al lector RF2: '+rf2_host+":"+rf2_port)
			logger.error (errorMsg)     

	if (config['RF3_ENABLE'] == "true"):
		try :
			s3.connect((rf3_host, int(rf3_port)))
			logger.info ('Conectado al lector RF3')
		except Exception, errorMsg:
			logger.error ('Error de conexion al lector RF3: '+rf3_host+":"+rf3_port)
			logger.error (errorMsg)     

	if (config['RF4_ENABLE'] == "true"):
		try :
			s4.connect((rf4_host, int(rf4_port)))
			logger.info ('Conectado al lector RF4')
		except Exception, errorMsg:
			logger.error ('Error de conexion al lector RF4: '+rf4_host+":"+rf4_port)
			logger.error (errorMsg)     

	while 1:
		try:
			socket_list = [sys.stdin, s1, s2, s3, s4]
	         
			# Get the list sockets which are readable
			read_sockets, write_sockets, error_sockets = select.select(socket_list , [], [])
	         
			for sock in read_sockets:
				try:
					if sock == s1:
						data1 = sock.recv(4096)
						logger.debug ("RF1: "+ data1)
						process_data(config['RF1_ID'], data1.split("\r"))
					elif sock == s2:
						data2 = sock.recv(4096)
						logger.debug ("RF2: "+ data2)
						process_data(config['RF2_ID'], data2.split("\r"))
					elif sock == s3:
						data3 = sock.recv(4096)
						logger.debug ("RF3: "+ data3)
						process_data(config['RF3_ID'], data3.split("\r"))
					elif sock == s4:
						data4 = sock.recv(4096)
						logger.debug ("RF4: "+ data4)
						process_data(config['RF4_ID'], data4.split("\r"))
				except Exception, e:
					print e
					pass
		except KeyboardInterrupt:
			logger.info ("FIN EJECUCION")
			disconnect_database()
			s1.close()
			s2.close()
			s3.close()
			s4.close()
			sys.exit(1)


if __name__ == '__main__':
    #test()
    main()

	