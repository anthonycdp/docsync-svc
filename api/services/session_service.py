import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
from pathlib import Path
import json
import threading

from ..models import SessionData, ExtractedData, TemplateType
from ..exceptions import SessionNotFoundError
from ..utils.logger import get_service_logger
from ..utils.helpers import SessionManager


class SessionService:
    
    def __init__(self, session_dir: Path = None, max_age_hours: int = 24):
        self.logger = get_service_logger('session')
        self.max_age_hours = max_age_hours
        self.session_dir = session_dir
        
        self._sessions: Dict[str, SessionData] = {}
        self._lock = threading.RLock()
        
        if self.session_dir:
            self.session_dir = Path(session_dir)
            self.session_dir.mkdir(parents=True, exist_ok=True)
    
    def create_session(
        self,
        extracted_data: ExtractedData,
        template_type: TemplateType,
        files_processed: int = 1
    ) -> str:
        session_id = SessionManager.generate_session_id()
        
        session = SessionData(
            session_id=session_id,
            extracted_data=extracted_data,
            template_type=template_type,
            files_processed=files_processed,
            timestamp=datetime.now(timezone.utc)
        )
        
        with self._lock:
            self._sessions[session_id] = session
        
        if self.session_dir:
            self._persist_session(session)
        
        self.logger.info(
            f"Session created: {session_id}",
            extra={
                "session_id": session_id,
                "template_type": template_type.value,
                "files_processed": files_processed
            }
        )
        
        return session_id
    
    def get_session(self, session_id: str) -> SessionData:
        # CKDEV-NOTE: Enhanced debug logging for session retrieval troubleshooting
        self.logger.info(f"Getting session: {session_id}")
        self.logger.info(f"Valid session ID format: {SessionManager.is_valid_session_id(session_id)}")
        self.logger.info(f"Sessions in memory: {list(self._sessions.keys())}")
        self.logger.info(f"Session dir configured: {self.session_dir}")
        
        if not SessionManager.is_valid_session_id(session_id):
            self.logger.error(f"Invalid session ID format: {session_id}")
            raise SessionNotFoundError(session_id)
        
        with self._lock:
            if session_id in self._sessions:
                self.logger.info(f"Found session in memory: {session_id}")
                session = self._sessions[session_id]
                
                self.logger.info(f"Session timestamp: {session.timestamp}")
                self.logger.info(f"Max age hours: {self.max_age_hours}")
                
                if session.is_expired(self.max_age_hours):
                    self.logger.warning(f"Session expired in memory: {session_id}")
                    self._cleanup_session(session_id)
                    raise SessionNotFoundError(session_id)
                
                self.logger.info(f"Returning valid session from memory: {session_id}")
                return session
        
        self.logger.info(f"Session not in memory, checking disk: {session_id}")
        
        if self.session_dir:
            session = self._load_session_from_disk(session_id)
            if session:
                self.logger.info(f"Found session on disk: {session_id}")
                
                if session.is_expired(self.max_age_hours):
                    self.logger.warning(f"Session expired on disk: {session_id}")
                    self._cleanup_session(session_id)
                    raise SessionNotFoundError(session_id)
                
                with self._lock:
                    self._sessions[session_id] = session
                
                self.logger.info(f"Loaded session from disk to memory: {session_id}")
                return session
            else:
                self.logger.warning(f"Session not found on disk: {session_id}")
        
        self.logger.error(f"Session not found anywhere: {session_id}")
        raise SessionNotFoundError(session_id)
    
    def update_session_data(self, session_id: str, field_path: str, value: str) -> SessionData:
        session = self.get_session(session_id)
        
        from ..utils.helpers import DataConverter
        success = DataConverter.update_extracted_data_field(
            session.extracted_data, field_path, value
        )
        
        if not success:
            raise ValueError(f"Failed to update field: {field_path}")
        
        from ..utils.validators import TemplateValidator
        session.validation_results = TemplateValidator.validate_for_template(
            session.extracted_data, session.template_type
        )
        
        with self._lock:
            self._sessions[session_id] = session
        
        if self.session_dir:
            self._persist_session(session)
        
        self.logger.info(
            f"Session data updated: {session_id}",
            extra={
                "session_id": session_id,
                "field": field_path,
                "value": value[:50] + "..." if len(value) > 50 else value
            }
        )
        
        return session
    
    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
        
        if self.session_dir:
            session_file = self.session_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
        
        self.logger.info(f"Session deleted: {session_id}")
        return True
    
    def cleanup_expired_sessions(self) -> int:
        expired_count = 0
        
        with self._lock:
            expired_sessions = [
                sid for sid, session in self._sessions.items()
                if session.is_expired(self.max_age_hours)
            ]
            
            for session_id in expired_sessions:
                self._cleanup_session(session_id)
                expired_count += 1
        
        if self.session_dir:
            for session_file in self.session_dir.glob("*.json"):
                try:
                    session = self._load_session_from_disk(session_file.stem)
                    if session and session.is_expired(self.max_age_hours):
                        session_file.unlink()
                        expired_count += 1
                except:
                    session_file.unlink()
                    expired_count += 1
        
        if expired_count > 0:
            self.logger.info(f"Cleaned up {expired_count} expired sessions")
        
        return expired_count
    
    def get_session_count(self) -> int:
        with self._lock:
            return len(self._sessions)
    
    def list_sessions(self, limit: int = 100) -> List[Dict[str, str]]:
        sessions = []
        
        with self._lock:
            for session_id, session in list(self._sessions.items())[:limit]:
                sessions.append({
                    "session_id": session_id,
                    "template_type": session.template_type.value,
                    "created": session.timestamp.isoformat(),
                    "files_processed": session.files_processed
                })
        
        return sessions
    
    def _persist_session(self, session: SessionData) -> None:
        if not self.session_dir:
            return
        
        session_file = self.session_dir / f"{session.session_id}.json"
        
        try:
            session_data = {
                "session_id": session.session_id,
                "template_type": session.template_type.value,
                "files_processed": session.files_processed,
                "timestamp": session.timestamp.isoformat(),
                "extracted_data": session.extracted_data.to_dict(),
                "validation_results": {
                    key: {
                        "status": result.status.value,
                        "message": result.message
                    }
                    for key, result in session.validation_results.items()
                }
            }
            
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to persist session {session.session_id}: {e}")
    
    def _load_session_from_disk(self, session_id: str) -> Optional[SessionData]:
        if not self.session_dir:
            return None
        
        session_file = self.session_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            from ..models import ValidationResult, ValidationStatus, TemplateType
            from ..models import ClientData, VehicleData, DocumentData, PaymentData, NewVehicleData, ThirdPartyData
            
            # CKDEV-NOTE: Enhanced reconstruction with backward compatibility
            extracted_data_dict = data.get("extracted_data", {})
            
            # Required fields with error handling
            client = ClientData(**extracted_data_dict.get("client", {}))
            vehicle = VehicleData(**extracted_data_dict.get("vehicle", {}))  
            document = DocumentData(**extracted_data_dict.get("document", {}))
            
            extracted_data = ExtractedData(
                client=client,
                vehicle=vehicle, 
                document=document
            )
            
            # Set optional fields if present with backward compatibility
            if extracted_data_dict.get("payment"):
                extracted_data.payment = PaymentData(**extracted_data_dict["payment"])
            
            if extracted_data_dict.get("new_vehicle"):
                # CKDEV-NOTE: Handle backward compatibility for NewVehicleData schema changes
                new_vehicle_data = extracted_data_dict["new_vehicle"]
                # Filter out any unknown fields to prevent __init__ errors
                valid_fields = {k: v for k, v in new_vehicle_data.items() 
                              if k in ['model', 'year_model', 'chassis', 'brand', 'plate', 'color', 'value', 'sales_order']}
                extracted_data.new_vehicle = NewVehicleData(**valid_fields)
            
            if extracted_data_dict.get("third_party"):
                extracted_data.third_party = ThirdPartyData(**extracted_data_dict["third_party"])
            
            validation_results = {}
            for key, result_data in data.get("validation_results", {}).items():
                validation_results[key] = ValidationResult(
                    status=ValidationStatus(result_data["status"]),
                    message=result_data["message"]
                )
            
            # CKDEV-NOTE: Ensure same TemplateType instance is used by finding by value
            template_type_value = data["template_type"]
            template_type = None
            for t_type in TemplateType:
                if t_type.value == template_type_value:
                    template_type = t_type
                    break
            
            if template_type is None:
                template_type = TemplateType(template_type_value)  # fallback
            
            session = SessionData(
                session_id=data["session_id"],
                extracted_data=extracted_data,
                template_type=template_type,
                files_processed=data["files_processed"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                validation_results=validation_results
            )
            
            return session
            
        except Exception as e:
            self.logger.error(f"Failed to load session {session_id} from disk: {e}")
            return None
    
    def _cleanup_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
        
        if self.session_dir:
            session_file = self.session_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()