#!/usr/bin/env python3
"""
proxy.py - HLS proxy básico usando aiohttp.

Instalación:
    pip install aiohttp uvloop backports.zstd

Uso:
    python3 proxy.py

Después reescribe las URLs del m3u8 para apuntar a:
    http://127.0.0.1:8080/proxy?url=<URL_ENCODED>

Este proxy añade automáticamente:
- Sec-Fetch-Site
- Referer
- Origin
- User-Agent
"""

from aiohttp import (

    web,
    ClientSession,
    TCPConnector,
    ClientConnectionResetError

)# Fin del import de aiohttp
from urllib.parse import (

    quote,
    unquote,
    urljoin

)#Fin del import del paquete URL
from yarl import URL
from LoggerMod import Logger
import re
import asyncio  
import uvloop
import socket
       
##############################################################################################
#
#                 General configuration
#
##############################################################################################
HOST="127.0.0.1"
PORT=8080
REFERER="https://animeav1.uns.bio/"
MAX_REINTENTOS = 3
RETARDO_REINTENTO = 4
#REFERER="https://ev-h.phncdn.com/hls/c6251/videos/202607/30/57207305/720P_4000K_57207305.mp4/"

HEADERS={

    "User-Agent":"Mozilla/5.0",
    "Sec-Fetch-Site":"same-origin",
    #"Referer": f"{REFERER}",
    #"Origin":"https://player.zilla-networks.com",
    #"Host": "p19-ad-site-sign-sg.tiktokcdn.com",
    "Accept": "*/*",
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "identity",
    #"DNT": "1",
    #"Alt-Used": "animeav1.uns.bio",
    #"Connection": "Keep-Alive",
    #"Sec-Fetch-Dest": "empty",
    #"Sec-Fetch-Mode": "cors",
    #"Priority": "u=4",
    #"TE": "trailers"

}

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

URI_RE=re.compile(

        r'URI="([^"]+)"',
        re.IGNORECASE

)# Fin de la inicialización del objeto de la clase re que identifica expresiones regulares1

SECUENCIA = bytes.fromhex("49 45 4e 44 ae 42 60 82 47 40") #Secuencia binaria que identifica cuando un servidor CDN está enviando video enmascarado de PNG
TAM_BUFFER = 200 # Max size of buffer in which the binary secuensce could be found.
session=None

class ConnectorDiagnostico(TCPConnector):
    def __init__(

        self,
        limite,
        limite_por_host,
        ttl_dns_cache_,
        max_time_alive

    ):# End of init definition
        super().__init__(

            limit=limite,
            limit_per_host = limite_por_host,
            ttl_dns_cache = ttl_dns_cache_,
            keepalive_timeout = max_time_alive

        )# End of init call
    #End of init function
    async def _create_connection(self, req, traces, timeout):

        Logger.info("Creando conexión para %s", req.url)
        transport = await super()._create_connection(

            req, 
            traces,
            timeout

        )# End of super call to base clase
        peer = transport.transport.get_extra_info("peername")
        ssl_object = transport.transport.get_extra_info("ssl_object")
        Logger.info("Peer remoto: %s", peer)
        if ssl_object is not None:
            Logger.info(

                "Versión TLS: %s",
                ssl_object.version()

            )# End of info call to Logger object
            Logger.info(

                "Cifrado TLS: %s",
                ssl_object.cipher()

            )# End of info call to Logger object
        # End of if block that makes sure ssl_object is not None
        else:
         Logger.info("No se encontró un objeto SSL en el transporte")
        return transport

    #End of function _create_connection
#End of custom class ConnectorDiagnostico

def fn_separate_signature( raw_url : str) -> tuple:
    """
    Utilidad que permite separar la parte de la firma en la URL original para
    que pueda ser procesada sin tocar la firma original.

    Parámetro único: URL completa original.
    Devuelve: una tupla con dos valores. El primero es la URL sin el parámetro 
    de firma hasta el signo de igual inclusive. El segundo es la firma tal cual.
    """
    i_wordSignatureIndex = raw_url.find('signature')
    i_signatureIndex = i_wordSignatureIndex + len('signature') + 1
    s_url_without_sig = raw_url[:i_signatureIndex]
    s_signature = quote(

        raw_url[ i_signatureIndex:],# it is totally necessary to unquote this part since request.query['url'] returns all the string decoded
        safe=""

    )# end of quote function
    return s_url_without_sig, s_signature 

def proxy_url(original_url):
    """
    Convierte
        https://....
    en
        http://127.0.0.1:8080/proxy?url=....
    """
    s_url_no_sig = None
    s_signa = ""
    if original_url.find('signature') != -1:

        s_url_no_sig, s_signa = fn_separate_signature( original_url )
        encoded = quote(s_url_no_sig, safe="")

    # End of if block that checks there is a signature parameter into the original URL
    else: # There is not any signature parameter into the original URL
     encoded = quote(original_url, safe="")
    return (

        f"http://{HOST}:{PORT}"
        f"/proxy/?url={encoded}{ s_signa }"

    )#Fin del statement return

def rewrite_playlist(txt):

    out=[]
    for line in txt.splitlines():

        s=line.strip()
        if not s:

            out.append(line)
            continue

        if s.startswith("#"):
            def repl(m):
            
                s_extracted_path = m.group(1) #.removeprefix(f"{REFERER}")
                Logger.info(f"\n\nEl objeto m es del tipo -> {type(m)}\nLos objetos contenidos dentro de m son:\n{dir(m)}\nEl valor de m tal cual es -> {m}\n")
                return f'URI="{ proxy_url( s_extracted_path ) }"' 
                #return f'URI="{proxy_url(urljoin(base,m.group(1)))}"'
                #s_path_without_domain = m.group(1).replace(unquote( proxy_url('http://127.0.0.1:8080/proxy/') ), '')
                #print( unquote( proxy_url('http://127.0.0.1:8080/proxy/') )) 
                #return f'URI="{ s_path_without_domain }"' #return f'URI="{proxy_url(urljoin(base,m.group(1)))}"'

            out.append(
                URI_RE.sub(

                    repl,
                    line

                ) if line.find( proxy_url('') ) == -1 else line# Fin del método sub de URI_RE
            )#Fin del método append
            continue

        #Fin del if que ejecuta cuando encuentra un comentario en el archivo.
        # Quita el dominio del servidor externo 
        if s.find( proxy_url('') ) == -1:
         out.append( proxy_url(s) )
        else:
         out.append( s )
        #s = s.replace( unquote( proxy_url('http://127.0.0.1:8080/proxy/') ), '' )
        #out.append( f"{s}" )

    #Fin del for que itera por todas las líneas de la respuesta.
    return "\n".join(out)

async def startup(app):

    global session
    #global Logger 
    connector = ConnectorDiagnostico(

        limite=0,
        limite_por_host=0,
        ttl_dns_cache_=300,
        max_time_alive=60

    )#Fin de la inicialización del objeto connector
    session=ClientSession(

        headers=HEADERS
        ,connector=connector

    )#Fin de la inicialización del objeto de sesión
    Logger.info(

        '\n'+"#"*100+'\n'
        +"#  Inicio de ejecución del servidor Proxy Versión 2.3\n"
        +"#"*100+'\n'

    )# Fin del log inicial

async def cleanup(app):
    await session.close()

def is_there_video( buffered_data: bytearray ) -> tuple:
    """
    Utilitary function that detects an specific binary secuence into the stream and bring back
    the index from where real video stream starts. In case there is not such binary secuences,
    the function brings back false and -1.

    Parameter: data buffer

    Bring back: A boolean indicating if binary secuence is into the buffer and an index from 
    we can split the buffer and take the real video data.
    """

    i_index_pos = -1
    if SECUENCIA in buffered_data:
     i_index_pos = buffered_data.find( SECUENCIA ) + 8
    return i_index_pos != -1, i_index_pos 

#.match_info["path"]
#.url
#.human_repr()
async def proxy(request):
    try:

        cabeceras = None # In order to add more headers to the request
        s_complete_url = request.query["url"]
        s_url_no_sig = None
        s_signa = ""
        url_decoded = None
        if s_complete_url.find('signature') != -1:

            s_url_no_sig, s_signa = fn_separate_signature( s_complete_url )
            url_decoded = unquote(s_url_no_sig)

        #End of if block that checks if there is a signature parameter into the original URL
        else:
         url_decoded = unquote( s_complete_url )#Fin de la función unquote
        url_raw = url_decoded + s_signa 
        url = URL( 

            url_raw,
            encoded=True

        )#End of URL object inicialization
        Logger.info(f"Se va a solicitar la siguiente URL -> {url}\n")
        if s_complete_url.find('tiktokcdn.com') != -1:
            DOMINIO = re.compile(
                
                r"^(?:https?://)?"
                r"(?P<dominio>"
                r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+"
                r"[a-zA-Z]{2,}"
                r")"

            )# End of re object instanciation
            cabeceras=HEADERS
            match = DOMINIO.match(url_raw)
            cabeceras['Host'] = match.group("dominio")

        #End of if block that checks if there is a tiktok CDN domain into the original URL
        #s_true_url = show_true_url(url)
        if cabeceras is not None:
            if cabeceras.get('Host'):
             del cabeceras['Host']
            #Logger.info("=============================== Cabeceras previo al request ====================")
            #for k, v in cabeceras.items():
            # Logger.info(f"El pinche diccionario tiene este header '{k}: {v}'")
        resp = await session.get(

            url,
            headers=cabeceras

        ) #End of get call
        if resp.status in (403, 429, 500, 502, 503, 504):

            retry_after = resp.headers.get("Retry-After")
            if retry_after is not None:

                Logger.warning("La solicitud ha fallado y el servidor ha devuelto un header Retry-After")
                try:

                    retardo = int(retry_after)
                    if retardo <= RETARDO_REINTENTO:
                     retardo = RETARDO_REINTENTO

                # End of try block 
                except ValueError:
                 retardo = RETARDO_REINTENTO

            # End of if block that processes a possible Retry-After header from the CDN server
            else:
             retardo = RETARDO_REINTENTO
            for intento in range(1, MAX_REINTENTOS + 1):

                await resp.release()
                Logger.warning(f"Proxy will wait for { retardo } seconds for next call to be performed.")
                await asyncio.sleep( retardo )
                resp = await session.get(url, headers=cabeceras) 
                if resp.status not in (403, 429, 500, 502, 503, 504):
                 intento = MAX_REINTENTOS + 2

            # End of block for that loops over the number of allowed retries
        #End of if block that prosceses possible throwtling scenarios
        async with resp:

            Logger.info(f"\nSe ha realizado el request sobre la URL '{url}'\nY el código de respuesta del servidor fue: {resp.status}")
            #Logger.info(f"El request hecho a la dirección '{url}'\nLlevó las cabeceras -> {resp.request_info.headers.items()}")
            ctype=resp.headers.get("Content-Type","")
            if "mpegurl" in ctype or url_raw.find("m3u8") != -1:

                Logger.info("La respuesta recibida fue un archivo index.")
                text=await resp.text()
                text=rewrite_playlist(text)
                return web.Response(text=text,content_type="application/vnd.apple.mpegurl")

            #Fin del if que sobreescribe archivos m3u8
            async def fn_send_first_data(

                dataStream, # Object that writes response to the client side
                b_is_fake: bool, # Flag that indicates if data has crap bytes at the beginnig
                i_vid_index: int, # index in which data flow is considered useful
                bufferedData: bytearray # Byte array that works as buffer for the first bytes of the stream

            ): # End of function definition
                if b_is_fake: #Splits initial crap PNG bytes

                    Logger.warning("Chunk has crap bytes at the beggingin. Getting rid of them...")
                    await dataStream.write( bufferedData[ i_vid_index:] )

                else: #sent first part of stream complete
                 await dataStream.write(bufferedData)

            #End of inner function fn_send_first_data
            buffer = bytearray() # somewhere in which the first bytes can be analized in search for the binari secuence.
            b_is_fake_png = False # Bandera que identifica si la descarga actual pertenece a un video con cabecera de imagen
            b_is_buffer_full = False # Flag to determine if buffer has reached the max size
            b_is_first_chunk_sent = False # Flag to indicate if the first buffer was sent.
            i_video_index = None # index in which real video data is ubicated into the buffer if any.
            stream=web.StreamResponse(status=resp.status)
            if ctype:
             stream.content_type=ctype.split(";")[0]
            await stream.prepare(request)
            try:
                async for chunk in resp.content.iter_chunked(65536):
                    if not b_is_first_chunk_sent:

                        buffer.extend(chunk)
                        if len(buffer) >= TAM_BUFFER:

                            b_is_buffer_full = True # Buffer is full
                            b_is_fake_png, i_video_index = is_there_video( buffer )

                        # End of if block that excecutes when buffer is equal or greater than max size
                    # End of if block that adds chunks to the buffer only if first set of data is not sent already
                    if b_is_buffer_full: #Writes data only if buffer is full
                        if not b_is_first_chunk_sent: #First set of data is not sent

                            b_is_first_chunk_sent = True
                            await fn_send_first_data(

                                stream,
                                b_is_fake_png,
                                i_video_index,
                                buffer

                            )# End of function call
                        # End of if block that bypass the first crap bytes of the video stream
                        else:
                         await stream.write(chunk)

                    # End of if block that writes the output only if buffer is full
                #End of block for in which stream is iterated and sended to the requester
                if not b_is_first_chunk_sent: #First set of data is not sent

                    Logger.warning("Requested information did not fullfil the buffer. Examinating if there is crap data...")
                    b_is_fake_png, i_video_index = is_there_video( buffer )
                    await fn_send_first_data(

                        stream,
                        b_is_fake_png,
                        i_video_index,
                        buffer

                    )# End of function call
                # End of if block that excecutes in case response is lower than necessary 200KB to fulfill the initial buffer
            # End of block try that catches client disconnections
            except (ClientConnectionResetError, ConnectionResetError):

                Logger.warning("El cliente es un pendejo que se desconectó antes. Cancelando descarga de datos...")
                return

            await stream.write_eof()
            return stream

        #fin del with que trabaja sobre la respuesta.
    #Fin del bloque try
    except KeyError as ex:

        Logger.exception(f"El request realizado no contiene el query parameter 'url' necesario para realizar la llamada al servidor externo.\n")
        return web.Response(text="Valió verga el request", content_type="text/plain", status=418)

    #End of except block that capture requests that do not have a required query parameter
    except Exception as ex:

        Logger.exception(f"El request realizado a la URL '{url}' ha fallado.\n")
        return web.Response(text="Valió verga el request", content_type="text/plain", status=500)

    # Fin del bloque except que captura la mayoría de las excepsiones.

async def fn_encode_http( request ):
    """
    Utility function that transforms an URL to one that is accepted by the proxy.
    To make use of it you must send a get request to http://127.0.0.1:8080/enconde?url=

    This function returns an http encoded string that points to the proxy endpoint. The function
    respects any signature contained into the URL.
    """
    try:

        s_complete_url = request.query["url"]
        s_addecuated_url = proxy_url( s_complete_url )
        return web.Response(

            text=s_addecuated_url + '\n', #Added an end of line for better elegance
            content_type="text/plain",
            status=200

        )# End of return statement
    # End of block try
    except KeyError as ex:

        Logger.exception(f"El request realizado no contiene el query parameter 'url' necesario para realizar la llamada al servidor externo.\n")
        return web.Response(text="Valió verga el request", content_type="text/plain", status=418)

    #End of except block that capture requests that do not have a required query parameter
    except Exception as ex:

        Logger.exception(f"El request realizado a la URL '{url}' ha fallado.\n")
        return web.Response(text="Valió verga el request", content_type="text/plain", status=500)

    # Fin del bloque except que captura la mayoría de las excepsiones.
# End of fn_encode_http function
###########################################################
# App inicialization
###########################################################
app=web.Application()
app.on_startup.append(startup)
app.on_cleanup.append(cleanup)
app.router.add_get("/proxy/{path:.*}",proxy)
app.router.add_get("/encode{path:.*}",fn_encode_http)

if __name__=="__main__":
    web.run_app(app,host=HOST,port=PORT)
