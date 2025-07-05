import boto3
import logging
from typing import Dict, Optional

logger = logging.getLogger('S3Hunter-X')

def check_bucket_access(bucket_url: str, aws_credentials: Optional[Dict] = None) -> Dict:
    """
    Verifica si un bucket S3 es accesible usando AWS SDK.
    
    Args:
        bucket_url (str): URL del bucket (e.g., bucket.s3.amazonaws.com).
        aws_credentials (Dict, optional): Credenciales AWS (access_key, secret_key).
    
    Returns:
        Dict: Detalles de accesibilidad (exists, is_public, owner, acls, error).
    """
    result = {"bucket_url": bucket_url, "exists": False, "is_public": False, "owner": None, "acls": None, "error": None}
    
    try:
        if not aws_credentials or not aws_credentials.get("access_key") or not aws_credentials.get("secret_key"):
            logger.debug(f"No se proporcionaron credenciales AWS para {bucket_url}")
            return result
        
        bucket_name = bucket_url.replace(".s3.amazonaws.com", "")
        session = boto3.Session(
            aws_access_key_id=aws_credentials["access_key"],
            aws_secret_access_key=aws_credentials["secret_key"]
        )
        s3_client = session.client("s3")
        
        s3_client.head_bucket(Bucket=bucket_name)
        result["exists"] = True
        
        try:
            acl = s3_client.get_bucket_acl(Bucket=bucket_name)
            result["owner"] = acl.get("Owner", {}).get("DisplayName", "unknown")
            result["acls"] = {
                "AllUsers": get_group_acls(acl, "AllUsers"),
                "AuthenticatedUsers": get_group_acls(acl, "AuthenticatedUsers")
            }
            result["is_public"] = bool(result["acls"]["AllUsers"])
        except Exception as e:
            result["acls"] = f"could not read: {str(e)}"
            logger.debug(f"No se pudieron leer ACLs para {bucket_name}: {e}")
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Error al verificar bucket {bucket_url}: {e}")
    
    return result

def get_group_acls(acl: Dict, group: str) -> str:
    """
    Extrae permisos ACL para un grupo específico.
    
    Args:
        acl (Dict): Datos ACL del bucket.
        group (str): Nombre del grupo (e.g., AllUsers, AuthenticatedUsers).
    
    Returns:
        str: Cadena de permisos ACL.
    """
    group_uri = f"http://acs.amazonaws.com/groups/global/{group}"
    perms = [g["Permission"] for g in acl.get("Grants", []) if g["Grantee"]["Type"] == "Group" and g["Grantee"]["URI"] == group_uri]
    return f"{group}: {', '.join(perms) if perms else '(none)'}"