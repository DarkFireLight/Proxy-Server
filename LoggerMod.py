# -*- coding: utf-8 -*-
"""
Author: David Padilla.

Módulo que puede agregarse al código principal para hacer que tu código logueé mensajes en archivos y salida estándar.
"""
import logging \
       ,logging.config

####################################################################################
#
#   Configuración principal de los logs.
#
####################################################################################
logging.config.dictConfig({

    "version": 1,
    "disable_existing_loggers": False,
    "formatters": { 
        "std": {
            "format": "%(asctime)s__%(levelname)s__encontrado en la línea -> %(lineno)d | %(message)s"
        }
    },
    "handlers": {
        "console": {

            "class": "logging.StreamHandler",
            "formatter": "std"

        },
        "file":{

            "class": "logging.FileHandler",
            "filename": "/home/david/david/Archivos Bash/Logs/ProxyLogs.log",
            "mode": "w",
            "formatter": "std",
            "encoding": "utf-8"

        }
    },# Final del diccionario de handlers
    "root": {
        
        "level": "INFO",
        "handlers": [

            "console",
            "file"

        ]
    },# Fin del diccionario que configura el logger para root
    "loggers": {
        "app.api": {
            "level": "DEBUG"
        }
    }
})# fin de la función de configuración logging.config.dictConfig
Logger = logging.getLogger(__name__)#Objeto que sirve para capturar logs.
