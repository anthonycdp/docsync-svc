from flask import Blueprint, request
from marshmallow import ValidationError as MarshmallowValidationError

from ..services import SessionService
from ..exceptions import SessionNotFoundError, ValidationError
from ..utils.helpers import ResponseBuilder, RequestHelper, DataConverter
from ..utils.validators import TemplateValidator
from ..utils.logger import get_api_logger
from ..models import SessionUpdateSchema


def create_session_controller(session_service: SessionService) -> Blueprint:
    bp = Blueprint('sessions', __name__, url_prefix='/api/sessions')
    logger = get_api_logger()
    
    @bp.route('/<session_id>', methods=['GET'])
    def get_session_data(session_id):
        try:
            # CKDEV-NOTE: Session data requested
            
            session = session_service.get_session(session_id)
            
            response_data = {
                "session_id": session_id,
                "template_type": session.template_type.value,
                "files_processed": session.files_processed,
                "timestamp": session.timestamp.isoformat(),
                "extracted_data": DataConverter.extracted_data_to_frontend_format(session.extracted_data),
                "validation_results": {
                    key: result.to_dict() for key, result in session.validation_results.items()
                }
            }
            
            return ResponseBuilder.success(data=response_data), 200
            
        except SessionNotFoundError:
            logger.warning(f"Session not found: {session_id}")
            return ResponseBuilder.error("Session not found"), 404
            
        except Exception as e:
            logger.error(f"Get session data failed: {e}")
            return ResponseBuilder.error("Failed to retrieve session data"), 500
    
    @bp.route('/<session_id>', methods=['PATCH'])
    def update_session_data(session_id):
        try:
            # CKDEV-NOTE: Session update requested
            
            schema = SessionUpdateSchema()
            try:
                data = schema.load(request.json)
            except MarshmallowValidationError as e:
                return ResponseBuilder.validation_error(e.messages), 400
            
            session = session_service.update_session_data(
                session_id=session_id,
                field_path=data['field'],
                value=data['value']
            )
            
            response_data = {
                "session_id": session_id,
                "updated_field": data['field'],
                "updated_value": data['value'],
                "extracted_data": DataConverter.extracted_data_to_frontend_format(session.extracted_data),
                "validation_results": {
                    key: result.to_dict() for key, result in session.validation_results.items()
                }
            }
            
            return ResponseBuilder.success(
                data=response_data,
                message=f"Field {data['field']} updated successfully"
            ), 200
            
        except SessionNotFoundError:
            return ResponseBuilder.error("Session not found"), 404
            
        except ValidationError as e:
            return ResponseBuilder.validation_error({"field": str(e)}), 400
            
        except ValueError as e:
            return ResponseBuilder.error(str(e)), 400
            
        except Exception as e:
            logger.error(f"Update session data failed: {e}")
            return ResponseBuilder.error("Failed to update session data"), 500
    
    @bp.route('/<session_id>', methods=['DELETE'])
    def delete_session(session_id):
        try:
            # CKDEV-NOTE: Session deletion requested
            
            success = session_service.delete_session(session_id)
            
            if success:
                return ResponseBuilder.success(
                    message=f"Session {session_id} deleted successfully"
                ), 200
            else:
                return ResponseBuilder.error("Failed to delete session"), 500
                
        except SessionNotFoundError:
            return ResponseBuilder.error("Session not found"), 404
            
        except Exception as e:
            logger.error(f"Delete session failed: {e}")
            return ResponseBuilder.error("Failed to delete session"), 500
    
    @bp.route('/<session_id>/validate', methods=['POST'])
    def validate_session_data(session_id):
        try:
            session = session_service.get_session(session_id)
            
            validation_results = TemplateValidator.validate_for_template(
                session.extracted_data, session.template_type
            )
            
            session.validation_results = validation_results
            
            is_valid = all(
                result.status.value == "valid" 
                for result in validation_results.values()
            )
            
            warnings_count = sum(
                1 for result in validation_results.values()
                if result.status.value == "warning"
            )
            
            errors_count = sum(
                1 for result in validation_results.values()
                if result.status.value == "invalid"
            )
            
            return ResponseBuilder.success(
                data={
                    "session_id": session_id,
                    "validation_results": {
                        key: result.to_dict() for key, result in validation_results.items()
                    },
                    "summary": {
                        "is_valid": is_valid,
                        "total_fields": len(validation_results),
                        "valid_fields": len(validation_results) - warnings_count - errors_count,
                        "warnings": warnings_count,
                        "errors": errors_count
                    }
                },
                message="Validation completed"
            ), 200
            
        except SessionNotFoundError:
            return ResponseBuilder.error("Session not found"), 404
            
        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return ResponseBuilder.error("Validation failed"), 500
    
    @bp.route('/list', methods=['GET'])
    def list_sessions():
        try:
            limit = int(request.args.get('limit', 50))
            if limit > 200:
                limit = 200
            
            sessions = session_service.list_sessions(limit)
            
            return ResponseBuilder.success(
                data={
                    "sessions": sessions,
                    "count": len(sessions),
                    "total_active": session_service.get_session_count()
                }
            ), 200
            
        except Exception as e:
            logger.error(f"List sessions failed: {e}")
            return ResponseBuilder.error("Failed to list sessions"), 500
    
    @bp.route('/cleanup', methods=['POST'])
    def cleanup_expired_sessions():
        try:
            cleaned_count = session_service.cleanup_expired_sessions()
            
            return ResponseBuilder.success(
                data={
                    "cleaned_sessions": cleaned_count,
                    "remaining_active": session_service.get_session_count()
                },
                message=f"Cleaned up {cleaned_count} expired sessions"
            ), 200
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            return ResponseBuilder.error("Cleanup failed"), 500
    
    @bp.route('/stats', methods=['GET'])
    def get_session_stats():
        try:
            stats = {
                "active_sessions": session_service.get_session_count(),
                "max_age_hours": session_service.max_age_hours
            }
            
            return ResponseBuilder.success(data=stats), 200
            
        except Exception as e:
            logger.error(f"Get session stats failed: {e}")
            return ResponseBuilder.error("Failed to get statistics"), 500
    
    return bp