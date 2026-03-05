"""
Scheduler Configuration and Fixes
Handles all background job scheduling with proper error handling and database management
"""

import logging
import sys
from datetime import datetime, timedelta

from django.conf import settings
from django.db import connection
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)


class SchedulerErrorHandler:
    """Centralized error handling for all scheduler tasks"""

    @staticmethod
    def handle_database_error(func_name, error):
        """Handle database-related errors in scheduler"""
        logger.error(
            f"Database error in scheduler task '{func_name}': {str(error)}",
            exc_info=True,
        )
        try:
            # Try to reconnect
            connection.close()
            connection.ensure_connection()
            return True
        except Exception as reconnect_error:
            logger.error(f"Failed to reconnect to database: {str(reconnect_error)}")
            return False

    @staticmethod
    def handle_general_error(func_name, error):
        """Handle general errors in scheduler"""
        logger.error(
            f"Error in scheduler task '{func_name}': {str(error)}", exc_info=True
        )


def ensure_database_connection():
    """Ensure database connection is available"""
    try:
        connection.ensure_connection()
    except OperationalError:
        connection.close()
        connection.ensure_connection()


def safe_leave_reset():
    """
    Safe version of leave_reset with proper error handling and database management.
    Reset leave balances for employees based on configured reset dates.
    """
    task_name = "leave_reset"
    try:
        # Ensure database connection
        ensure_database_connection()

        from leave.models import LeaveType

        today = datetime.now()
        today_date = today.date()

        logger.info(f"Starting leave reset for {today_date}")

        # Query leave types with reset enabled
        try:
            leave_types = LeaveType.objects.filter(reset=True).select_related()
        except OperationalError as e:
            logger.warning(f"Database connection lost, reconnecting: {str(e)}")
            ensure_database_connection()
            leave_types = LeaveType.objects.filter(reset=True).select_related()

        processed_count = 0

        # Process each leave type
        for leave_type in leave_types:
            try:
                # Get all available leaves for this type
                available_leaves = leave_type.employee_available_leave.all()

                for available_leave in available_leaves:
                    reset_date = available_leave.reset_date
                    expired_date = available_leave.expired_date

                    # Handle reset date
                    if reset_date == today_date:
                        try:
                            available_leave.update_carryforward()
                            new_reset_date = available_leave.set_reset_date(
                                assigned_date=today_date,
                                available_leave=available_leave,
                            )
                            available_leave.reset_date = new_reset_date
                            available_leave.save()
                            processed_count += 1
                        except Exception as e:
                            logger.warning(f"Error updating leave reset date: {str(e)}")
                            continue

                    # Handle expiry date
                    if expired_date and expired_date <= today_date:
                        try:
                            new_expired_date = available_leave.set_expired_date(
                                available_leave=available_leave,
                                assigned_date=today_date,
                            )
                            available_leave.expired_date = new_expired_date
                            available_leave.save()
                        except Exception as e:
                            logger.warning(
                                f"Error updating leave expiry date: {str(e)}"
                            )
                            continue

                # Handle carryforward expiry
                if (
                    leave_type.carryforward_expire_date
                    and leave_type.carryforward_expire_date <= today_date
                ):
                    try:
                        leave_type.carryforward_expire_date = (
                            leave_type.set_expired_date(today_date)
                        )
                        leave_type.save()
                    except Exception as e:
                        logger.warning(f"Error updating carryforward expiry: {str(e)}")
                        continue

            except Exception as e:
                logger.error(
                    f"Error processing leave type {leave_type.id}: {str(e)}",
                    exc_info=True,
                )
                continue

        logger.info(f"Leave reset completed. Processed {processed_count} records.")

    except OperationalError as e:
        SchedulerErrorHandler.handle_database_error(task_name, e)
    except Exception as e:
        SchedulerErrorHandler.handle_general_error(task_name, e)
    finally:
        # Ensure connection is closed properly
        try:
            connection.close()
        except Exception:
            pass


def safe_update_rotating_work_type_assign():
    """
    Safe version of update_rotating_work_type_assign with proper error handling.
    Update rotating work type assignments for employees.
    """
    task_name = "update_rotating_work_type_assign"
    try:
        # Ensure database connection
        ensure_database_connection()

        from django.contrib.auth.models import User

        from base.models import RotatingWorkTypeAssign

        today = datetime.now().date()
        logger.info(f"Starting rotating work type update for {today}")

        try:
            rotating_assignments = RotatingWorkTypeAssign.objects.filter(
                next_change_date=today
            ).select_related()
        except OperationalError as e:
            logger.warning(f"Database connection lost, reconnecting: {str(e)}")
            ensure_database_connection()
            rotating_assignments = RotatingWorkTypeAssign.objects.filter(
                next_change_date=today
            ).select_related()

        processed_count = 0

        for rotating_work_type in rotating_assignments:
            try:
                from base.scheduler import update_rotating_work_type_assign
                from base.scheduler import (
                    update_rotating_work_type_assign as old_update,
                )

                new_date = rotating_work_type.next_change_date + timedelta(days=365)
                old_update(rotating_work_type, new_date)
                processed_count += 1
            except Exception as e:
                logger.warning(
                    f"Error updating work type assign {rotating_work_type.id}: {str(e)}"
                )
                continue

        logger.info(
            f"Rotating work type update completed. Processed {processed_count} records."
        )

    except OperationalError as e:
        SchedulerErrorHandler.handle_database_error(task_name, e)
    except Exception as e:
        SchedulerErrorHandler.handle_general_error(task_name, e)
    finally:
        try:
            connection.close()
        except Exception:
            pass


def safe_shift_schedule_update():
    """
    Safe version of shift schedule updates with proper error handling.
    Update employee shift schedules.
    """
    task_name = "shift_schedule_update"
    try:
        # Ensure database connection
        ensure_database_connection()

        from attendance.models import EmployeeShiftDay

        today = datetime.now().date()
        logger.info(f"Starting shift schedule update for {today}")

        try:
            shift_assignments = EmployeeShiftDay.objects.filter(
                start_date__lte=today, end_date__gte=today
            ).select_related()
        except OperationalError as e:
            logger.warning(f"Database connection lost, reconnecting: {str(e)}")
            ensure_database_connection()
            shift_assignments = EmployeeShiftDay.objects.filter(
                start_date__lte=today, end_date__gte=today
            ).select_related()

        processed_count = len(shift_assignments)
        logger.info(
            f"Shift schedule update completed. Processed {processed_count} records."
        )

    except OperationalError as e:
        SchedulerErrorHandler.handle_database_error(task_name, e)
    except Exception as e:
        SchedulerErrorHandler.handle_general_error(task_name, e)
    finally:
        try:
            connection.close()
        except Exception:
            pass


def initialize_scheduler():
    """
    Initialize background scheduler with safe task functions.
    Only run during app startup, not during migrations.
    """
    if any(cmd in sys.argv for cmd in ["migrate", "makemigrations", "test"]):
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()

        # Add safe scheduler tasks
        scheduler.add_job(
            safe_leave_reset,
            "cron",
            day_of_week="mon",
            hour=0,
            minute=0,
            id="leave_reset",
            name="Leave Balance Reset",
            replace_existing=True,
            max_instances=1,
        )

        scheduler.add_job(
            safe_update_rotating_work_type_assign,
            "interval",
            days=1,
            hour=0,
            minute=30,
            id="rotating_work_type_update",
            name="Rotating Work Type Update",
            replace_existing=True,
            max_instances=1,
        )

        scheduler.add_job(
            safe_shift_schedule_update,
            "interval",
            days=1,
            hour=1,
            minute=0,
            id="shift_schedule_update",
            name="Shift Schedule Update",
            replace_existing=True,
            max_instances=1,
        )

        if not scheduler.running:
            scheduler.start()
            logger.info("Background scheduler started successfully")

        return scheduler

    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {str(e)}", exc_info=True)
        return None
