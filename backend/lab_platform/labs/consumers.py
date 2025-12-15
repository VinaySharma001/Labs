# backend/labs/consumers.py
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
import docker
import socket

logger = logging.getLogger(__name__)
client = docker.from_env()

class LabTerminalConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            # url route param name: 'name' (or 'container' depending on your routing)
            self.name = self.scope['url_route']['kwargs']['name']
            logger.info(f"WebSocket connection attempt for container: {self.name}")
            
            # Accept the connection first
            await self.accept()
            logger.info(f"WebSocket connection accepted for container: {self.name}")

            # Initialize attributes
            self.container = None
            self.exec_id = None
            self.sock = None
            self.raw_sock = None
            self._reader_task = None

            # get container object
            try:
                self.container = client.containers.get(self.name)
                logger.info(f"Container found: {self.name}")
            except docker.errors.NotFound:
                error_msg = f"Container '{self.name}' not found"
                logger.error(error_msg)
                await self.send(f"❌ {error_msg}\r\n")
                await self.close()
                return
            except Exception as e:
                error_msg = f"Error getting container: {e}"
                logger.error(error_msg)
                await self.send(f"❌ {error_msg}\r\n")
                await self.close()
                return

            # Check if container is running
            if self.container.status != 'running':
                error_msg = f"Container '{self.name}' is not running (status: {self.container.status})"
                logger.error(error_msg)
                await self.send(f"❌ {error_msg}\r\n")
                await self.close()
                return

            # create an interactive exec (pty)
            try:
                exec_obj = client.api.exec_create(
                    container=self.container.id,
                    cmd=["/bin/bash", "-i"],  # Use -i for interactive mode
                    tty=True,
                    stdin=True,
                    stdout=True,
                    stderr=True
                )
                self.exec_id = exec_obj['Id']
                logger.info(f"Exec created: {self.exec_id}")
            except Exception as e:
                error_msg = f"Error creating exec: {e}"
                logger.error(error_msg)
                await self.send(f"❌ {error_msg}\r\n")
                await self.close()
                return

            # exec_start with socket=True returns a dockerpy socket wrapper
            try:
                self.sock = client.api.exec_start(self.exec_id, tty=True, socket=True)
                
                # On some docker-py versions exec_start returns a Multiplexed socket object;
                # the real socket is available at attribute ._sock (or ._sock if wrapped).
                # We'll try to get the raw socket:
                raw = getattr(self.sock, "_sock", None)
                if raw is None:
                    # fallback: try attribute 'sock' or assume sock is raw already
                    raw = getattr(self.sock, "sock", self.sock)
                self.raw_sock = raw  # this is a real socket.socket instance

                # Log socket type and attributes for debugging
                logger.info(f"Socket type: {type(self.raw_sock)}")
                logger.info(f"Socket attributes: {dir(self.raw_sock)[:20]}")

                # Make socket blocking for recv/send operations
                try:
                    self.raw_sock.setblocking(True)
                    logger.info("Socket set to blocking mode")
                except Exception as e:
                    logger.warning(f"Could not set socket blocking: {e}")

                logger.info("Socket initialized successfully")
            except Exception as e:
                error_msg = f"Error starting exec: {e}"
                logger.error(error_msg)
                await self.send(f"❌ {error_msg}\r\n")
                await self.close()
                return

            # Start a background reader using executor so it doesn't block the event loop
            try:
                # Store the event loop reference before starting the executor
                self._event_loop = asyncio.get_event_loop()
                self._reader_task = self._event_loop.run_in_executor(None, self._read_from_docker)
                logger.info("Background reader task started")
            except Exception as e:
                error_msg = f"Error starting reader task: {e}"
                logger.error(error_msg)
                await self.send(f"❌ {error_msg}\r\n")
                await self.close()
                return

            # notify client
            await self.send("✅ Connected to container shell\r\n$ ")
            logger.info(f"Successfully connected to container: {self.name}")
            
        except Exception as e:
            error_msg = f"Unexpected error in connect: {e}"
            logger.exception(error_msg)
            try:
                await self.send(f"❌ {error_msg}\r\n")
            except:
                pass
            try:
                await self.close()
            except:
                pass

    def _read_from_docker(self):
        """Blocking read executed in a thread via run_in_executor."""
        try:
            logger.info("Starting to read from Docker socket")
            while True:
                # recv from real socket; this blocks inside the executor thread only
                data = self.raw_sock.recv(4096)
                if not data:
                    logger.info("Received empty data, socket closed")
                    break
                logger.info(f"Received {len(data)} bytes from Docker: {repr(data[:50])}")
                # schedule send to websocket on the main loop (use stored loop reference)
                coro = self.send(data.decode(errors="ignore"))
                asyncio.run_coroutine_threadsafe(coro, self._event_loop)
        except Exception as e:
            logger.exception(f"Error in _read_from_docker: {e}")
            # socket closed or error — try to notify client (safe best-effort)
            try:
                coro = self.send(f"\r\n[connection to container closed: {e}]\r\n")
                asyncio.run_coroutine_threadsafe(coro, self._event_loop)
            except Exception:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        """Receive data from browser (keystrokes)."""
        logger.info(f"Received data - text_data: {repr(text_data) if text_data else None}, bytes_data: {bytes_data is not None}")
        
        # Handle both text and binary data
        data_to_send = None
        if bytes_data:
            data_to_send = bytes_data
            logger.info(f"Using bytes_data, length: {len(bytes_data)}")
        elif text_data:
            data_to_send = text_data.encode('utf-8')
            logger.info(f"Using text_data, encoded length: {len(data_to_send)}, original: {repr(text_data)}")
        else:
            logger.warning("No data received in receive()")
            return
        
        if not hasattr(self, 'raw_sock') or not self.raw_sock:
            error_msg = "Socket not initialized"
            logger.error(error_msg)
            await self.send(f"\r\n[error: {error_msg}]\r\n")
            return
        
        try:
            # Write to socket in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._write_to_docker, data_to_send)
            logger.info(f"Successfully wrote {len(data_to_send)} bytes to Docker socket")
        except Exception as e:
            error_msg = f"Error writing to Docker: {e}"
            logger.exception(error_msg)
            await self.send(f"\r\n[write error: {e}]\r\n")
    
    def _write_to_docker(self, data):
        """Blocking write executed in a thread via run_in_executor."""
        try:
            logger.info(f"Writing {len(data)} bytes to Docker socket: {repr(data[:50])}")
            if hasattr(self.raw_sock, "sendall"):
                self.raw_sock.sendall(data)
            else:
                self.raw_sock.send(data)
            logger.info("Successfully sent data to Docker socket")
        except (BrokenPipeError, OSError) as e:
            error_msg = f"Socket error: {e}"
            logger.error(error_msg)
            # Try to notify the client
            try:
                coro = self.send(f"\r\n[socket error: {e}]\r\n")
                asyncio.run_coroutine_threadsafe(coro, asyncio.get_event_loop())
            except Exception:
                pass
        except Exception as e:
            error_msg = f"Unexpected error in _write_to_docker: {e}"
            logger.exception(error_msg)

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnecting for container: {getattr(self, 'name', 'unknown')}, code: {close_code}")
        try:
            # Cancel reader task if it exists
            if hasattr(self, '_reader_task') and self._reader_task:
                try:
                    self._reader_task.cancel()
                except Exception as e:
                    logger.warning(f"Error canceling reader task: {e}")
            
            # close raw socket
            if hasattr(self, 'raw_sock') and self.raw_sock:
                try:
                    self.raw_sock.shutdown(socket.SHUT_RDWR)
                except Exception as e:
                    logger.debug(f"Error shutting down socket: {e}")
                try:
                    self.raw_sock.close()
                except Exception as e:
                    logger.debug(f"Error closing socket: {e}")
        except Exception as e:
            logger.warning(f"Error in disconnect: {e}")
