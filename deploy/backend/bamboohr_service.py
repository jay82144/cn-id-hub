"""
BambooHR Integration Service for Identity & Employee Hub

Syncs employee data from BambooHR to the local employee directory.
Uses the BambooHR API v2 datasets endpoint.

Configuration required in Settings:
- bamboohr_subdomain: Company subdomain (e.g., 'penrosehealth')
- bamboohr_api_key: API key from BambooHR
- bamboohr_enabled: Whether sync is enabled
"""

import os
import logging
import base64
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BambooHRConfig(BaseModel):
    """BambooHR configuration"""
    subdomain: str
    api_key: str
    enabled: bool = True


class BambooHREmployee(BaseModel):
    """Employee data from BambooHR"""
    eeid: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    preferredName: Optional[str] = None
    email: Optional[str] = None
    jobInformationJobTitle: Optional[str] = None
    jobInformationDivision: Optional[str] = None
    jobInformationReportsTo: Optional[str] = None
    teams: Optional[List[str]] = None
    employmentStatus: Optional[str] = None
    gender: Optional[str] = None
    dateOfBirth: Optional[str] = None
    hireDate: Optional[str] = None
    isSupervisor: Optional[bool] = None
    supervisorEid: Optional[str] = None
    status: Optional[str] = None


class BambooHRSyncResult(BaseModel):
    """Result of a BambooHR sync operation"""
    success: bool
    message: str
    total_fetched: int = 0
    created: int = 0
    updated: int = 0
    errors: List[str] = []
    sync_time: str = ""


class BambooHRService:
    """Service for interacting with BambooHR API"""
    
    # Fields to request from BambooHR
    EMPLOYEE_FIELDS = [
        "firstName",
        "lastName",
        "preferredName",
        "jobInformationReportsTo",
        "jobInformationJobTitle",
        "jobInformationDivision",
        "teams",
        "employmentStatus",
        "gender",
        "dateOfBirth",
        "hireDate",
        "eeid",
        "isSupervisor",
        "supervisorEid",
        "status",
        "email"
    ]
    
    def __init__(self, config: BambooHRConfig):
        self.config = config
        self.base_url = f"https://{config.subdomain}.bamboohr.com/api/v2"
        
        # Create Basic auth header (api_key:x - BambooHR uses API key as username)
        auth_string = f"{config.api_key}:x"
        auth_bytes = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        self.auth_header = f"Basic {auth_bytes}"
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to BambooHR API"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Try to fetch a small batch to test connection
                response = await client.post(
                    f"{self.base_url}/datasets/employee/data",
                    headers={
                        "Authorization": self.auth_header,
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    },
                    json={
                        "page": 1,
                        "pageSize": 1,
                        "fields": ["firstName", "lastName"],
                        "filter": "status in ('Active')"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message": "Connection successful",
                        "total_employees": data.get("totalCount", 0)
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "message": "Authentication failed - check your API key"
                    }
                elif response.status_code == 403:
                    return {
                        "success": False,
                        "message": "Access denied - API key may not have required permissions"
                    }
                else:
                    return {
                        "success": False,
                        "message": f"API error: {response.status_code} - {response.text}"
                    }
        except httpx.ConnectError:
            return {
                "success": False,
                "message": f"Could not connect to {self.config.subdomain}.bamboohr.com - check subdomain"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection error: {str(e)}"
            }
    
    async def fetch_employees(
        self,
        page: int = 1,
        page_size: int = 100,
        status_filter: str = "Active"
    ) -> Dict[str, Any]:
        """
        Fetch employees from BambooHR
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of employees per page (max 100)
            status_filter: Filter by status ('Active', 'Inactive', or both)
        
        Returns:
            Dict with employees list and pagination info
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {
                    "page": page,
                    "pageSize": min(page_size, 100),  # BambooHR max is 100
                    "fields": self.EMPLOYEE_FIELDS,
                    "filter": f"status in ('{status_filter}')"
                }
                
                response = await client.post(
                    f"{self.base_url}/datasets/employee/data",
                    headers={
                        "Authorization": self.auth_header,
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                if response.status_code != 200:
                    logger.error(f"BambooHR API error: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                        "employees": [],
                        "total": 0
                    }
                
                data = response.json()
                
                # Parse employees from response
                # BambooHR returns data in format: {"data": [{"fields": {...}}, ...]}
                employees = []
                for emp_data in data.get("data", []):
                    try:
                        # Extract fields - BambooHR nests data under "fields" key
                        fields = emp_data.get("fields", emp_data)
                        employee = BambooHREmployee(**fields)
                        employees.append(employee)
                    except Exception as e:
                        logger.warning(f"Failed to parse employee: {e}")
                
                return {
                    "success": True,
                    "employees": employees,
                    "total": data.get("totalCount", len(employees)),
                    "page": page,
                    "page_size": page_size,
                    "has_more": len(employees) == page_size
                }
                
        except Exception as e:
            logger.error(f"Error fetching employees from BambooHR: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "employees": [],
                "total": 0
            }
    
    async def fetch_all_employees(self, status_filter: str = "Active") -> List[BambooHREmployee]:
        """Fetch all employees (handles pagination)"""
        all_employees = []
        page = 1
        page_size = 100
        
        while True:
            result = await self.fetch_employees(page, page_size, status_filter)
            
            if not result["success"]:
                logger.error(f"Failed to fetch page {page}: {result.get('error')}")
                break
            
            all_employees.extend(result["employees"])
            
            if not result.get("has_more", False):
                break
            
            page += 1
            
            # Safety limit
            if page > 100:
                logger.warning("Reached page limit (100), stopping pagination")
                break
        
        return all_employees


async def sync_bamboohr_employees(
    config: BambooHRConfig,
    db_session,
    company_id: str
) -> BambooHRSyncResult:
    """
    Sync employees from BambooHR to local database
    
    Args:
        config: BambooHR configuration
        db_session: Database session
        company_id: Company ID to associate employees with
    
    Returns:
        BambooHRSyncResult with sync statistics
    """
    from sqlalchemy import select
    from models import Employee, EmployeeStatus
    import uuid
    
    service = BambooHRService(config)
    
    # Test connection first
    test_result = await service.test_connection()
    if not test_result["success"]:
        return BambooHRSyncResult(
            success=False,
            message=test_result["message"],
            sync_time=datetime.now(timezone.utc).isoformat()
        )
    
    # Fetch all employees
    logger.info("Starting BambooHR employee sync...")
    employees = await service.fetch_all_employees()
    
    if not employees:
        return BambooHRSyncResult(
            success=True,
            message="No employees found in BambooHR",
            total_fetched=0,
            sync_time=datetime.now(timezone.utc).isoformat()
        )
    
    created = 0
    updated = 0
    errors = []
    
    for bamboo_emp in employees:
        try:
            # Generate a placeholder email if not provided
            emp_email = bamboo_emp.email
            if not emp_email and bamboo_emp.eeid:
                # Use bamboo ID as a placeholder for employees without email
                emp_email = f"employee_{bamboo_emp.eeid}@bamboohr.placeholder"
            
            # Skip if we still don't have an identifier
            if not emp_email and not bamboo_emp.eeid:
                continue
            
            # Check if employee exists by bamboo_id
            existing = await db_session.execute(
                select(Employee).where(Employee.bamboo_id == bamboo_emp.eeid)
            )
            employee = existing.scalar_one_or_none()
            
            # If not found by bamboo_id, try by email (if real email)
            if not employee and bamboo_emp.email:
                existing = await db_session.execute(
                    select(Employee).where(Employee.email == bamboo_emp.email)
                )
                employee = existing.scalar_one_or_none()
            
            # Parse hire date
            hire_date = None
            if bamboo_emp.hireDate:
                try:
                    hire_date = datetime.strptime(bamboo_emp.hireDate, "%Y-%m-%d")
                except:
                    pass
            
            # Determine status
            status = EmployeeStatus.ACTIVE if bamboo_emp.status == "Active" else EmployeeStatus.ARCHIVED
            
            # Get team (first team if multiple)
            team = None
            if bamboo_emp.teams and len(bamboo_emp.teams) > 0:
                team = bamboo_emp.teams[0]
            
            if employee:
                # Update existing employee
                employee.first_name = bamboo_emp.firstName or employee.first_name
                employee.last_name = bamboo_emp.lastName or employee.last_name
                employee.job_title = bamboo_emp.jobInformationJobTitle
                employee.department = bamboo_emp.jobInformationDivision
                employee.team = team
                employee.hire_date = hire_date
                employee.status = status
                employee.bamboo_id = bamboo_emp.eeid
                employee.company_id = uuid.UUID(company_id)
                # Update email only if we have a real one
                if bamboo_emp.email:
                    employee.email = bamboo_emp.email
                updated += 1
            else:
                # Create new employee
                new_employee = Employee(
                    email=emp_email,
                    first_name=bamboo_emp.firstName or "",
                    last_name=bamboo_emp.lastName or "",
                    job_title=bamboo_emp.jobInformationJobTitle,
                    department=bamboo_emp.jobInformationDivision,
                    team=team,
                    hire_date=hire_date,
                    status=status,
                    bamboo_id=bamboo_emp.eeid,
                    company_id=uuid.UUID(company_id)
                )
                db_session.add(new_employee)
                created += 1
                
        except Exception as e:
            error_msg = f"Error syncing {bamboo_emp.email or bamboo_emp.eeid}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    await db_session.commit()
    
    return BambooHRSyncResult(
        success=True,
        message=f"Sync completed: {created} created, {updated} updated",
        total_fetched=len(employees),
        created=created,
        updated=updated,
        errors=errors,
        sync_time=datetime.now(timezone.utc).isoformat()
    )
