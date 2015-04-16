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
import Orange

from pylab import *
from matplotlib.patches import Ellipse

########################################################################
from configobj import ConfigObj
config = ConfigObj("./Kyros_indoor.conf")

kcs_host = config['KCS_HOST']
kcs_port = config['KCS_PORT']


########################################################################
LOG = "./indoor.log"
LOG_FOR_ROTATE = 30

conDB = None
socketKCS = None

dataTraining = None
classifierKyros = None

rf_readers = []
thread_readers = []
t = None 

data_strength  = [0] * 100

TAG_ID = '00056760';
tag_strength  = ['?'] * 5
tag_strength[0] = '?'
tag_strength[1] = '?'
tag_strength[2] = '?'
tag_strength[3] = '?'
tag_strength[4] = '?'
 
zona0_lat = '4130.9503'
zona0_lon = '00443.2828'
zonaA_lat = '4130.9533'
zonaA_lon = '00443.2842'
zonaB_lat = '4130.9492'
zonaB_lon = '00443.2846'
zonaC_lat = '4130.9505'
zonaC_lon = '00443.2830'
zonaD_lat = '4130.9468'
zonaD_lon = '00443.2805'
zonaE_lat = '4130.9480'
zonaE_lon = '00443.2786'
zonaF_lat = '4130.9503'
zonaF_lon = '00443.2788'
zonaG_lat = '4130.9500'
zonaG_lon = '00443.2762'
zonaH_lat = '4130.9518'
zonaH_lon = '00443.2866'

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

class Reader():
	reader_id = None
	host = None
	port = None
	easting = None
	northing = None
	def __init__(self, reader_id, host, port, easting, northing):
		self.reader_id = reader_id
		self.host = host
		self.port = port
		self.easting = easting
		self.northing = northing


class ReaderThread(threading.Thread):  
	def __init__(self, reader_id, host, port):  
		threading.Thread.__init__(self)  
		self.reader_id = reader_id  
		self.host = host  
		self.port = port 
	def run(self):  
		logger.debug ("Hilo lanzado para el Reader_ID: " + str(self.reader_id))
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.settimeout(20)
		try :
			s.connect((self.host, self.port))
			s.send("g,LOCATE,04,0,1,1\n")
			s.send("u,82\n")
			s.send("s,1\n")
			s.send("m,433\n")
			logger.info ('Conectado al lector RF: ' + str(self.reader_id))
			while 1:
				tagdata = s.recv(4096)
				#if (self.reader_id==0):
				#logger.debug ("RF "+ str(self.reader_id) + ":" + tagdata)
				process_data(self.reader_id, tagdata.split("\r"))

		except Exception, errorMsg:
			logger.error ('Error de conexion al lector RF: '+str(self.host)+":"+str(self.port))
			logger.error (errorMsg)  


def test():
	logger.info ("START TEST")

	data = Orange.data.Table("training0.tab")
	classifier = Orange.classification.bayes.NaiveLearner(data)

	d = data[0]
	m = d
	m[0] = '89'
	m[1] = '71'
	m[2] = '86'
	m[3] = '81'
	print m
	print classifier(m)
	
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
		socketKCS.sendall("IMEI=56760\r\n")
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

def trilateracion(a,b,c):
    """se localiza el dispositivo por medio de las
   fuerzas de las senales captadas y de la ubicacion de
   las antenas
    """
    d = 3
    i = 2.5
    j = -4
    #se definen las coordenadas de la Antena A
    ax = 0
    ay = 0
    #se define la cobertura Antena A
    ar = a
    #se definen las coordenadas de la Antena B
    bx = d
    by = 0
    #se definen las coordenadas de la Antena C
    br = b
    cx = i
    cy = j
    #se define la cobertura de la Antena c
    cr = c
    #se localiza la ubicacion del receptor
    x = (ar**2 - br**2 + d**2)/float((2*d))
    y = ((ar**2-br**2+i**2+j**2)/(2*j))-((float(i/j))*x)
    print "Tu estas ubicado en -> (%s,%s)" %(x, y)
    

def read_readers_conf():
	global rf_readers
	global conDB

	db_ip = config['DB_IP']
	db_port = config['DB_PORT']
	db_name = config['DB_NAME']
	db_user = config['DB_USER']
	db_passwd = config['DB_PASSWD']

	try:
		conDB = mdb.connect(db_ip, db_user, db_passwd, db_name)
		cur = conDB.cursor()
		query = "Select READER_ID, HOST, PORT, EASTING, NORTING from READER where TIPO=1"
		cur.execute(query)
		numrows = int(cur.rowcount)
		for i in range(numrows):
			row = cur.fetchone()
			#print row
			reader = Reader(int(row[0]), row[1], int(row[2]), float(row[3]), float(row[4]))
			rf_readers.append(reader)
	except mdb.Error, e:
		print "Error %d: %s" % (e.args[0], e.args[1])

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
	global rf_readers
	global data_strength
	global socketKCS
	global tag_strength

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
					if (tag_id == TAG_ID):
						tag_strength[reader_id] = str(strength)

						#print str(reader_id) + " - " + str(strength)
						data_strength[reader_id] = strength
						sum_strength = data_strength[1]+data_strength[2]+data_strength[3]+data_strength[4]
						#lat = (float(rf_lat[1])*data_strength[1] + float(rf_lat[2])*data_strength[2] + float(rf_lat[3])*data_strength[3] + float(rf_lat[4])*data_strength[4])/sum_strength
						#lon = (float(rf_lon[1])*data_strength[1] + float(rf_lon[2])*data_strength[2] + float(rf_lon[3])*data_strength[3] + float(rf_lon[4])*data_strength[4])/sum_strength
						#print ("-->"+str(lat)+","+str(lon))
						#coordenadas = transform_utm_to_wgs84(lat,lon,30)
						#print str(coordenadas[1]) + "," + str(coordenadas[0])
						#trama = str(tag_id) +","+str(milisegundos)+","+str(lon)+","+str(lat)+",20,246,14,9,2,0.0,0.9,3836"+'\r\n'
						#socketKCS.sendall(trama)


		except Exception,e:
			print e 
			pass
	
class TagThread(threading.Thread):  
	def __init__(self):  
		threading.Thread.__init__(self)  
	def run(self):  
		logger.debug ("Hilo para escribir los datos de entrenamiento")

		global dataTraining
		global classifierKyros
		global socketKCS

		try :
			
			while 1:
				
				d = dataTraining[0]
				m = d
				m[0] = tag_strength[0]
				m[1] = tag_strength[1]
				m[2] = tag_strength[2]
				m[3] = tag_strength[3]
				m[4] = '?'
				#print m
				logger.info (m)
				zona = str(classifierKyros(m))
				
				logger.info ("--> ZONA:"+zona)
			
				TAG_ID2 = '56760'
				#milisegundos = calendar.timegm(time.gmtime())
				hora_actual = time.strftime("%d%m%y-%H%M%S.000", time.localtime())
				vhora_actual = hora_actual.split('-')
				if (zona=='A'):
					tramaGPRMC = "GPRMC," + vhora_actual[1]+",A,"+zonaA_lat+",N,"+zonaA_lon+",W,12.73,169.22,"+vhora_actual[0]+",,\r\n"
				elif (zona=='B'):
					tramaGPRMC = "GPRMC," + vhora_actual[1]+",A,"+zonaB_lat+",N,"+zonaB_lon+",W,12.73,169.22,"+vhora_actual[0]+",,\r\n"
				elif (zona=='C'):
					tramaGPRMC = "GPRMC," + vhora_actual[1]+",A,"+zonaC_lat+",N,"+zonaC_lon+",W,12.73,169.22,"+vhora_actual[0]+",,\r\n"
				elif (zona=='D'):
					tramaGPRMC = "GPRMC," + vhora_actual[1]+",A,"+zonaD_lat+",N,"+zonaD_lon+",W,12.73,169.22,"+vhora_actual[0]+",,\r\n"
				elif (zona=='E'):
					tramaGPRMC = "GPRMC," + vhora_actual[1]+",A,"+zonaE_lat+",N,"+zonaE_lon+",W,12.73,169.22,"+vhora_actual[0]+",,\r\n"
				elif (zona=='F'):
					tramaGPRMC = "GPRMC," + vhora_actual[1]+",A,"+zonaF_lat+",N,"+zonaF_lon+",W,12.73,169.22,"+vhora_actual[0]+",,\r\n"
				elif (zona=='G'):
					tramaGPRMC = "GPRMC," + vhora_actual[1]+",A,"+zonaG_lat+",N,"+zonaG_lon+",W,12.73,169.22,"+vhora_actual[0]+",,\r\n"
				elif (zona=='H'):
					tramaGPRMC = "GPRMC," + vhora_actual[1]+",A,"+zonaH_lat+",N,"+zonaH_lon+",W,12.73,169.22,"+vhora_actual[0]+",,\r\n"
				else:
					tramaGPRMC = "GPRMC," + vhora_actual[1]+",A,"+zona0_lat+",N,"+zona0_lon+",W,12.73,169.22,"+vhora_actual[0]+",,\r\n"
				
				logger.info (tramaGPRMC)			

				socketKCS.sendall(tramaGPRMC)
				time.sleep(11)

		except Exception, errorMsg:
			logger.error ('Error ')
			logger.error (errorMsg)  

def main():
	global rf_readers
	global thread_readers
	global dataTraining
	global classifierKyros
	global t

	hora_actual = time.strftime("20%y/%m/%d %H:%M:%S", time.localtime())
	logger.info ("START - "+hora_actual)


	dataTraining = Orange.data.Table("training0.tab")
	classifierKyros = Orange.classification.bayes.NaiveLearner(dataTraining)

	connect_database()
	connect_kcs()
	read_readers_conf()

	# Lanzar los hilos para los lectores
	for reader in rf_readers:
		r = ReaderThread(int(reader.reader_id)-1, reader.host, reader.port)  
		r.start()  
		#r.join()
		thread_readers.append(r)

	# Lanzar hilo para el tag
	t = TagThread()
	t.start()

	
	while 1:
		comando = raw_input("Comando: ")
		
		if (comando == "exit"):
			for t_reader in thread_readers:
				if t_reader.isAlive():
					try:
						t_reader._Thread__stop()
  					except:
  						print(str(t_reader.getName()) + ' could not be terminated')
  			
			if t.isAlive():
				try:
					t._Thread__stop()
  				except:
  					print(str(t.getName()) + ' could not be terminated')
  			
			sys.exit(1)
	


if __name__ == '__main__':
    #test()
    main()

	