#!/usr/bin/env python
#-*- coding: UTF-8 -*-

import time
import datetime
import os 
import logging, logging.handlers
import socket, select, string, sys

import threading  


########################################################################


########################################################################
LOG = "./recoge_datos_indoor.log"
LOG_FOR_ROTATE = 30

rf_readers = []
thread_readers = []
thread_training_file = None

tagA_strength  = ['?'] * 5
tagB_strength  = ['?'] * 5
tagC_strength  = ['?'] * 5
tagD_strength  = ['?'] * 5
tagE_strength  = ['?'] * 5
tagF_strength  = ['?'] * 5
tagG_strength  = ['?'] * 5
tagH_strength  = ['?'] * 5

tagA = '00077642';
tagB = '00066398';
tagC = '00066390';
tagD = '00088382';
tagE = '00077639';
tagF = '00077525';
tagG = '00066374';
tagH = '00066387';

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
	def __init__(self, reader_id, host, port):
		self.reader_id = reader_id
		self.host = host
		self.port = port

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
				data = s.recv(4096)
				logger.debug ("RF "+ str(self.reader_id) + ":" + data)
				process_data(self.reader_id, data.split("\r"))

		except Exception, errorMsg:
			logger.error ('Error de conexion al lector RF: '+str(self.host)+":"+str(self.port))
			logger.error (errorMsg)  


class WriteDataTrainingThread(threading.Thread):  
	def __init__(self):  
		threading.Thread.__init__(self)  
	def run(self):  
		logger.debug ("Hilo para escribir los datos de entrenamiento")

		try :
			while 1:
				fichero_entrenamiento = open('./training.tab', 'a')		
				fichero_entrenamiento.writelines('%s	%s	%s	%s	A\n' %(tagA_strength[0],tagA_strength[1],tagA_strength[2],tagA_strength[3]))
				fichero_entrenamiento.writelines('%s	%s	%s	%s	B\n' %(tagB_strength[0],tagB_strength[1],tagB_strength[2],tagB_strength[3]))
				fichero_entrenamiento.writelines('%s	%s	%s	%s	C\n' %(tagC_strength[0],tagC_strength[1],tagC_strength[2],tagC_strength[3]))
				fichero_entrenamiento.writelines('%s	%s	%s	%s	D\n' %(tagD_strength[0],tagD_strength[1],tagD_strength[2],tagD_strength[3]))
				fichero_entrenamiento.writelines('%s	%s	%s	%s	E\n' %(tagE_strength[0],tagE_strength[1],tagE_strength[2],tagE_strength[3]))
				fichero_entrenamiento.writelines('%s	%s	%s	%s	F\n' %(tagF_strength[0],tagF_strength[1],tagF_strength[2],tagF_strength[3]))
				fichero_entrenamiento.writelines('%s	%s	%s	%s	G\n' %(tagG_strength[0],tagG_strength[1],tagG_strength[2],tagG_strength[3]))
				fichero_entrenamiento.writelines('%s	%s	%s	%s	H\n' %(tagH_strength[0],tagH_strength[1],tagH_strength[2],tagH_strength[3]))
				fichero_entrenamiento.close()
				time.sleep (15)
		except Exception, errorMsg:
			logger.error ('Error al escribir datos de entrenamiento')
			logger.error (errorMsg)  

def test():
	logger.info ("START TEST")
	
def process_data(reader_id,data):
	global rf_readers
	global tagA_strength
	global tagB_strength
	global tagC_strength
	global tagD_strength
	global tagE_strength
	global tagF_strength
	global tagG_strength
	global tagH_strength

	for msg in data:
		try:
			if (len(str(msg)))>0:
				v_msg = msg.split(",")
				#if (v_msg[0]=='H' and len(v_msg)==5):
				if (v_msg[0]=='H'):
					tag_id = v_msg[1]
					reader_id = int(reader_id)
					strength = v_msg[5]
					strength = int(strength[1:len(strength)])
					
					#print reader_id

					if (tag_id == tagA):
						tagA_strength[reader_id] = strength
					elif (tag_id == tagB):
						tagB_strength[reader_id] = strength
					elif (tag_id == tagC):
						tagC_strength[reader_id] = strength
					elif (tag_id == tagD):
						tagD_strength[reader_id] = strength
					elif (tag_id == tagE):
						tagE_strength[reader_id] = strength
					elif (tag_id == tagF):
						tagF_strength[reader_id] = strength
					elif (tag_id == tagG):
						tagG_strength[reader_id] = strength
					elif (tag_id == tagH):
						tagH_strength[reader_id] = strength
					else:
						pass

		except Exception,e:
			print e 
			pass
		
def main():
	global rf_readers
	global thread_readers
	global thread_training_file

	hora_actual = time.strftime("20%y/%m/%d %H:%M:%S", time.localtime())
	logger.info ("START - "+hora_actual)

	reader1 = Reader(int(0), '172.26.0.81', 6500)
	reader2 = Reader(int(1), '172.26.0.82', 6500)
	reader3 = Reader(int(2), '172.26.0.83', 6500)
	reader4 = Reader(int(3), '172.26.0.84', 6500)
			
	rf_readers.append(reader1)
	rf_readers.append(reader2)
	rf_readers.append(reader3)
	rf_readers.append(reader4)

	# fichero de training
	fichero_entrenamiento = open('./training.tab', 'w')
	cabecera1 = "reader1"+"\t"+"reader2"+"\t"+"reader3"+"\t"+"reader4"+"\t"+"zona\n"
	cabecera2 = "continuous"+"\t"+"continuous"+"\t"+"continuous"+"\t"+"continuous"+"\t"+"discrete\n"
	cabecera3 = "\t\t\t\t"+"class\n"
	fichero_entrenamiento.writelines(cabecera1)
	fichero_entrenamiento.writelines(cabecera2)
	fichero_entrenamiento.writelines(cabecera3)
	fichero_entrenamiento.close()

	# Lanzar los hilos para los lectores
	for reader in rf_readers:
		r = ReaderThread(reader.reader_id, reader.host, reader.port)  
		r.start()  
		thread_readers.append(r)

	# Lanzar el hilo que recopila datos de entrenamiento
	thread_training_file = WriteDataTrainingThread()
	thread_training_file.start()

	while 1:
		comando = raw_input("Comando: ")
		
		if (comando == "exit"):
			for t_reader in thread_readers:
				if t_reader.isAlive():
					try:
						t_reader._Thread__stop()
  					except:
  						print(str(t_reader.getName()) + ' could not be terminated')

  			if thread_training_file.isAlive():
  				try:
					thread_training_file._Thread__stop()
  				except:
  					print(str(thread_training_file.getName()) + ' could not be terminated')

			sys.exit(1)
	
if __name__ == '__main__':
    #test()
    main()