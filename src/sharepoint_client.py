"""
SharePoint klient pro upload souborů z Spinoco.
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
import structlog
from office365.runtime.auth.authentication_context import AuthenticationContext
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File
from office365.sharepoint.folders.folder import Folder

from .config import settings


class SharePointClient:
    """
    Klient pro upload souborů na SharePoint.
    
    Podporuje autentifikaci pomocí username/password a upload souborů
    do specifikované složky na SharePoint Online.
    """
    
    def __init__(
        self,
        site_url: str,
        client_id: str = None,
        client_secret: str = None,
        tenant_id: str = None,
        username: str = None,
        password: str = None,
        folder_path: str = "/Shared Documents/Spinoco Calls"
    ):
        self.site_url = site_url.rstrip('/')
        self.folder_path = folder_path.strip('/')
        self.logger = structlog.get_logger("sharepoint_client")
        
        # OAuth2 credentials
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        
        # Legacy credentials
        self.username = username
        self.password = password
        
        self._ctx: Optional[ClientContext] = None
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # SharePoint klient nemusí explicitně zavírat spojení
        pass
    
    async def connect(self):
        """Připojí se k SharePoint a ověří přístup."""
        try:
            self.logger.info("Připojuji se k SharePoint", site_url=self.site_url)
            
            if self.client_id and self.client_secret and self.tenant_id:
                # OAuth2 autentifikace
                self.logger.info("Používám OAuth2 autentifikaci")
                from office365.runtime.auth.client_credential import ClientCredential
                
                credentials = ClientCredential(self.client_id, self.client_secret)
                self._ctx = ClientContext(self.site_url).with_credentials(credentials)
                
            elif self.username and self.password:
                # Legacy username/password autentifikace
                self.logger.info("Používám legacy username/password autentifikaci")
                auth_ctx = AuthenticationContext(self.site_url)
                
                if auth_ctx.acquire_token_for_user(self.username, self.password):
                    self._ctx = ClientContext(self.site_url, auth_ctx)
                else:
                    raise Exception("Nepodařilo se ověřit přihlašovací údaje")
            else:
                raise Exception("Chybí přihlašovací údaje (OAuth2 nebo username/password)")
            
            # Otestuj spojení
            web = self._ctx.web
            self._ctx.load(web)
            self._ctx.execute_query()
            
            auth_method = "OAuth2" if self.client_id else "Legacy"
            self.logger.info(
                "Úspěšně připojen k SharePoint",
                site_title=web.properties.get('Title', 'Unknown'),
                auth_method=auth_method
            )
                
        except Exception as e:
            self.logger.error("Chyba při připojení k SharePoint", error=str(e))
            raise
    
    async def ensure_folder_exists(self, folder_path: str) -> Folder:
        """
        Zajistí, že složka existuje (vytvoří ji pokud neexistuje).
        
        Args:
            folder_path: Cesta ke složce (relativní k site)
            
        Returns:
            Folder: SharePoint folder objekt
        """
        if not self._ctx:
            raise Exception("Není připojen k SharePoint")
        
        try:
            # Normalizuj cestu
            folder_path = folder_path.strip('/').replace('\\', '/')
            
            self.logger.debug("Kontroluji existenci složky", folder_path=folder_path)
            
            # Zkus získat složku
            try:
                folder = self._ctx.web.get_folder_by_server_relative_url(f"/{folder_path}")
                self._ctx.load(folder)
                self._ctx.execute_query()
                
                self.logger.debug("Složka existuje", folder_path=folder_path)
                return folder
                
            except Exception:
                # Složka neexistuje, vytvoř ji
                self.logger.info("Vytvářím složku", folder_path=folder_path)
                
                # Rozděl cestu na části
                path_parts = folder_path.split('/')
                current_path = ""
                
                for part in path_parts:
                    if not part:
                        continue
                    
                    current_path = f"{current_path}/{part}" if current_path else part
                    
                    try:
                        # Zkus získat aktuální složku
                        test_folder = self._ctx.web.get_folder_by_server_relative_url(f"/{current_path}")
                        self._ctx.load(test_folder)
                        self._ctx.execute_query()
                    except Exception:
                        # Složka neexistuje, vytvoř ji
                        parent_path = "/".join(current_path.split('/')[:-1])
                        if parent_path:
                            parent_folder = self._ctx.web.get_folder_by_server_relative_url(f"/{parent_path}")
                        else:
                            parent_folder = self._ctx.web.root_folder
                        
                        self._ctx.load(parent_folder)
                        self._ctx.execute_query()
                        
                        new_folder = parent_folder.folders.add(part)
                        self._ctx.execute_query()
                        
                        self.logger.debug("Vytvořena podsložka", path=current_path)
                
                # Získej finální složku
                folder = self._ctx.web.get_folder_by_server_relative_url(f"/{folder_path}")
                self._ctx.load(folder)
                self._ctx.execute_query()
                
                self.logger.info("Složka úspěšně vytvořena", folder_path=folder_path)
                return folder
                
        except Exception as e:
            self.logger.error("Chyba při vytváření složky", folder_path=folder_path, error=str(e))
            raise
    
    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        folder_path: Optional[str] = None,
        overwrite: bool = True
    ) -> Dict[str, Any]:
        """
        Nahraje soubor na SharePoint.
        
        Args:
            file_content: Binární obsah souboru
            filename: Název souboru
            folder_path: Cesta ke složce (None = použije default)
            overwrite: Přepsat existující soubor
            
        Returns:
            Dict: Informace o nahraném souboru
        """
        if not self._ctx:
            raise Exception("Není připojen k SharePoint")
        
        target_folder = folder_path or self.folder_path
        
        try:
            self.logger.info(
                "Nahrávám soubor na SharePoint",
                filename=filename,
                folder_path=target_folder,
                size_bytes=len(file_content)
            )
            
            # Zajisti existenci složky
            folder = await self.ensure_folder_exists(target_folder)
            
            # Nahraj soubor
            if overwrite:
                # Přepiš existující soubor
                target_file = folder.upload_file(filename, file_content)
            else:
                # Nepřepisuj, vyhoď chybu pokud existuje
                try:
                    existing_file = folder.files.get_by_url(filename)
                    self._ctx.load(existing_file)
                    self._ctx.execute_query()
                    raise Exception(f"Soubor {filename} již existuje")
                except Exception as e:
                    if "does not exist" not in str(e).lower():
                        raise
                    # Soubor neexistuje, můžeme nahrát
                    target_file = folder.upload_file(filename, file_content)
            
            self._ctx.execute_query()
            
            # Získej informace o nahraném souboru
            self._ctx.load(target_file)
            self._ctx.execute_query()
            
            file_info = {
                "name": target_file.properties.get("Name"),
                "url": target_file.properties.get("ServerRelativeUrl"),
                "size": target_file.properties.get("Length"),
                "created": target_file.properties.get("TimeCreated"),
                "modified": target_file.properties.get("TimeLastModified"),
                "folder_path": target_folder
            }
            
            self.logger.info(
                "Soubor úspěšně nahrán",
                filename=filename,
                url=file_info["url"],
                size=file_info["size"]
            )
            
            return file_info
            
        except Exception as e:
            self.logger.error(
                "Chyba při nahrávání souboru",
                filename=filename,
                folder_path=target_folder,
                error=str(e)
            )
            raise
    
    async def file_exists(self, filename: str, folder_path: Optional[str] = None) -> bool:
        """
        Kontroluje, zda soubor existuje na SharePoint.
        
        Args:
            filename: Název souboru
            folder_path: Cesta ke složce (None = použije default)
            
        Returns:
            bool: True pokud soubor existuje
        """
        if not self._ctx:
            raise Exception("Není připojen k SharePoint")
        
        target_folder = folder_path or self.folder_path
        
        try:
            folder = self._ctx.web.get_folder_by_server_relative_url(f"/{target_folder}")
            file_obj = folder.files.get_by_url(filename)
            self._ctx.load(file_obj)
            self._ctx.execute_query()
            
            return True
            
        except Exception:
            return False
    
    async def get_file_info(self, filename: str, folder_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Získá informace o souboru na SharePoint.
        
        Args:
            filename: Název souboru
            folder_path: Cesta ke složce (None = použije default)
            
        Returns:
            Dict: Informace o souboru nebo None pokud neexistuje
        """
        if not self._ctx:
            raise Exception("Není připojen k SharePoint")
        
        target_folder = folder_path or self.folder_path
        
        try:
            folder = self._ctx.web.get_folder_by_server_relative_url(f"/{target_folder}")
            file_obj = folder.files.get_by_url(filename)
            self._ctx.load(file_obj)
            self._ctx.execute_query()
            
            return {
                "name": file_obj.properties.get("Name"),
                "url": file_obj.properties.get("ServerRelativeUrl"),
                "size": file_obj.properties.get("Length"),
                "created": file_obj.properties.get("TimeCreated"),
                "modified": file_obj.properties.get("TimeLastModified"),
                "folder_path": target_folder
            }
            
        except Exception:
            return None
    
    async def list_files(self, folder_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Vypíše všechny soubory ve složce.
        
        Args:
            folder_path: Cesta ke složce (None = použije default)
            
        Returns:
            List[Dict]: Seznam souborů s jejich informacemi
        """
        if not self._ctx:
            raise Exception("Není připojen k SharePoint")
        
        target_folder = folder_path or self.folder_path
        
        try:
            folder = self._ctx.web.get_folder_by_server_relative_url(f"/{target_folder}")
            files = folder.files
            self._ctx.load(files)
            self._ctx.execute_query()
            
            file_list = []
            for file_obj in files:
                file_list.append({
                    "name": file_obj.properties.get("Name"),
                    "url": file_obj.properties.get("ServerRelativeUrl"),
                    "size": file_obj.properties.get("Length"),
                    "created": file_obj.properties.get("TimeCreated"),
                    "modified": file_obj.properties.get("TimeLastModified")
                })
            
            return file_list
            
        except Exception as e:
            self.logger.error(
                "Chyba při získávání seznamu souborů",
                folder_path=target_folder,
                error=str(e)
            )
            raise
    
    def create_folder_structure_from_template(
        self,
        template: str,
        task_data: Dict[str, Any]
    ) -> str:
        """
        Vytvoří strukturu složek podle template.
        
        Args:
            template: Template pro cestu (např. "{{due_date|yyyy}}/{{due_date|MM}}/{{call_from}}")
            task_data: Data úkolu pro substituci
            
        Returns:
            str: Výsledná cesta ke složce
        """
        try:
            # Zde by byla logika pro parsing template
            # Pro jednoduchost zatím vrátíme základní cestu
            from datetime import datetime
            
            # Základní substituce
            result = template
            if "{{due_date|yyyy}}" in result:
                year = datetime.now().strftime("%Y")
                result = result.replace("{{due_date|yyyy}}", year)
            
            if "{{due_date|MM}}" in result:
                month = datetime.now().strftime("%m")
                result = result.replace("{{due_date|MM}}", month)
            
            # Kombinuj s base folder path
            if self.folder_path:
                result = f"{self.folder_path}/{result}"
            
            return result.strip('/')
            
        except Exception as e:
            self.logger.warning(
                "Chyba při vytváření folder structure",
                template=template,
                error=str(e)
            )
            return self.folder_path
