# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from apps.home import blueprint
from flask import render_template, request, jsonify, flash, redirect, url_for, Blueprint, Response
from flask_login import login_required
from jinja2 import TemplateNotFound
from apps.config import Config
import requests
import random
from werkzeug.utils import secure_filename
import csv 
from io import StringIO
import math
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from dateutil.parser import parse
from flask import Flask

app = Flask(__name__)

blueprint = Blueprint('home_blueprint', __name__)


@blueprint.route('/index', methods=['GET'])
@login_required
def index():
    try:
        card_count = requests.get(Config.API_URL + '/api/cards/count',timeout=10).json()
        driver_count = requests.get(Config.API_URL + '/api/drivers/count',timeout=10).json()
        vehicle_count = requests.get(Config.API_URL + '/api/vehicles/count',timeout=10).json()
        distance_weekly = requests.get(Config.API_URL + '/api/trips/weekly',timeout=10).json()
        distance_monthly = requests.get(Config.API_URL + '/api/trips/monthly',timeout=10).json()
        fuel_weekly = requests.get(Config.API_URL + '/api/fuel_refills/weekly',timeout=10).json()
        fuel_monthly = requests.get(Config.API_URL + '/api/fuel_refills/monthly',timeout=10).json()
        average_weekly = round(distance_weekly/fuel_weekly,2) if fuel_weekly != 0 else 0
        average_monthly = round(distance_monthly/fuel_monthly,2) if fuel_monthly != 0 else 0
        trips = view_trips()[3]
        performance_data = driver_performance()
        vehicle_performance_data = vehicle_performance()
        pending_drivers_data = pending_drivers()
        if not isinstance(performance_data, (list, dict)):
            performance_data = []  # Or set it to a default value or handle accordingly
        if not isinstance(vehicle_performance_data, (list, dict)):
            vehicle_performance_data = []  # Same here
        return render_template('home/index.html',
                            card_count= card_count, 
                            driver_count=driver_count, 
                            vehicle_count=vehicle_count, 
                            distance_weekly=distance_weekly, 
                            distance_monthly=distance_monthly, 
                            fuel_monthly= fuel_monthly, 
                            fuel_weekly = fuel_weekly,
                            average_weekly = average_weekly,
                            average_monthly = average_monthly,
                            trips = trips,
                            performance_data = performance_data or [],
                            vehicle_performance_data = vehicle_performance_data or [],
                            pending_drivers = pending_drivers_data)  # Redirect to updated list
    except Exception as e:
        return render_template('home/index.html'), 500

@blueprint.route('/<template>', methods=["GET"])
@blueprint.route('/<template>.html', methods=["GET"])  # Handle both '/drivers' and '/drivers.html'
@login_required
def route_template(template):
    try:
        # Ensure the template ends with '.html'
        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page (segment)
        segment = get_segment(request)

        # Render the template with the detected segment
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        # If the template is not found, render a 404 error page
        return render_template('home/page-404.html'), 404

    except Exception:
        # Catch any other exceptions and render a 500 error page
        return render_template('home/page-500.html'), 500


@blueprint.route('/vehicles', methods=['GET'])
@login_required
def view_vehicles():
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Fetch data from the API
        responses = requests.get(Config.API_URL + '/api/vehicles', timeout=10)
        vehicles = responses.json()
        # Pagination logic
        total_records = len(vehicles)
        total_pages = (total_records + per_page - 1) // per_page  # Calculate total pages
        start_record = (page - 1) * per_page
        end_record = min(start_record + per_page, total_records)

        # Slice the data based on pagination
        paginated_vehicles = vehicles[start_record:end_record]
        return render_template(
            "home/tbl_vehicles.html", 
            vehicles=paginated_vehicles,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            total_records=total_records,
            start_record=start_record + 1,
            end_record=end_record
        )

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)})

@blueprint.route('/vehicles/add', methods=['POST'])
@login_required
def add_vehicle():

    try:
        make = request.form.get('make')
        model = request.form.get('model')
        regn_no = request.form.get('regn_no')
        fuel_type = request.form.get('fuel_type')
        tank_cap = request.form.get('tank_cap')
        chassis_no = request.form.get('chassis_no')
        engine_no = request.form.get('engine_no')
        ins_expiry = request.form.get('ins_expiry')
        files = request.files.get('files')

        # Handle file upload if needed
        if files:
            filename = regn_no
    
        data = {
            "make": make,
            "model": model,
            "regn_no": regn_no,
            "fuel_type": fuel_type,
            "tank_cap": tank_cap,
            "chassis_no": chassis_no,
            "engine_no": engine_no,
            "ins_expiry": ins_expiry,
        }
        uploaded_files = request.files.getlist('files')  # Get multiple files
        files = []
        
        if uploaded_files:
            try:
                for file in uploaded_files:
                    if file and file.filename:  # Ensure file is not empty
                        filename = secure_filename(file.filename)
                        files.append(('files', (filename, file, file.content_type)))  # Append each file
            except Exception as e:
                flash(f"Error uploading files: {str(e)}", "danger")
                return redirect(url_for('home_blueprint.view_drivers'))
        else:
            flash("No files uploaded", "danger")
            return redirect(url_for('home_blueprint.view_drivers'))  # Redirect if no files uploaded

        # Send the request with multiple files
        response = requests.post(Config.API_URL + '/api/vehicles/add', data=data, files=files, timeout=10)
        
        if response.status_code == 200:
            return redirect(url_for('home_blueprint.view_vehicles'))
        else:
            flash(f"Error: {response.json()}", "danger")
            return redirect(url_for('home_blueprint.view_vehicles'))
            
    except requests.exceptions.RequestException as e:
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for('home_blueprint.view_vehicles'))  # Redirect to updated list


@blueprint.route('/vehicles/edit/<int:id>', methods=['GET'])
@login_required
def edit_vehicle(id):
    try:
        response = requests.get(Config.API_URL+'/api/vehicles/'+str(id), timeout=10)
        vehicle = response.json()
        return render_template("home/edit_vehicle.html", vehicle=vehicle)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)})


@blueprint.route('/vehicles/delete/<int:id>', methods=['POST'])
@login_required
def delete_vehicle(id):
    try:
        response = requests.post(Config.API_URL + '/api/vehicles/delete/' + str(id), timeout=10)
        
        if response.status_code == 200:
            flash("Vehicle deleted successfully!", "success")
        else:
            flash("Error deleting driver. Please try again.", "danger")
            
    except requests.exceptions.RequestException as e:
        flash(f"Error: {str(e)}", "danger")
    
    return redirect(url_for('home_blueprint.view_vehicles'))

# Helper - Extract current page name from request
@blueprint.route('/vehicles/update/<int:id>', methods=['POST'])
@login_required
def update_vehicle(id):
    try:
        make = request.form.get('make')
        model = request.form.get('model')
        fuel_type = request.form.get('fuel_type')
        tank_cap = request.form.get('tank_cap')
        regn_no = request.form.get('regn_no')
        chassis_no = request.form.get('chassis_no')
        engine_no = request.form.get('engine_no')
        ins_expiry = request.form.get('ins_expiry')
        data = {
        "id":id,
        "make": make,
        "model": model,
        "fuel_type":fuel_type,
        "tank_cap":tank_cap,
        "regn_no": regn_no,
        "chassis_no": chassis_no,
        "engine_no": engine_no,
        "ins_expiry": ins_expiry,
        }
        uploaded_files = request.files.getlist('files')  # Get multiple files
        files = []
        if uploaded_files:
            try:
                for file in uploaded_files:
                    if file and file.filename:  # Ensure file is not empty
                        filename = secure_filename(file.filename)
                        files.append(('files', (filename, file, file.content_type)))  # Append each file
            except Exception as e:
                flash(f"Error uploading files: {str(e)}", "danger")
                return redirect(url_for('home_blueprint.view_vehicles'))
        else:
            flash("No files uploaded", "danger")
            return redirect(url_for('home_blueprint.view_vehicles'))  # Redirect if no files uploaded

        # Send the request with multiple files
        response = requests.post(Config.API_URL + '/api/vehicles/update/'+str(id), data=data, files=files, timeout=10)
        
        if response.status_code == 200:
            return redirect(url_for('home_blueprint.view_vehicles'))
        else:
            flash(f"Error: {response.json()}", "danger")
            return redirect(url_for('home_blueprint.view_vehicles'))
            
    except requests.exceptions.RequestException as e:
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for('home_blueprint.view_vehicles'))  # Redirect to updated list

@blueprint.route('/vehicles/download', methods=['GET'])
@login_required
def download_vehicles():
    try:
        # Fetch vehicle data from the external API
        api_response = requests.get(Config.API_URL + '/api/vehicles', timeout=10)

        # Check if the response is valid and contains JSON data
        json_data = api_response.json()
        if not json_data:
            flash('No data found to download', 'warning')
            return redirect(url_for('home_blueprint.view_vehicles'))
        
        # Generate CSV data to download
        def generate_csv():
            # Create a StringIO buffer to hold CSV data
            csv_buffer = StringIO()
            csv_writer = csv.writer(csv_buffer)

            # Write the header (keys from the first dictionary item)
            headers = json_data[0].keys()  # Assuming the JSON data is a list of dicts
            csv_writer.writerow(headers)

            # Write the rows (values from each dictionary)
            for entry in json_data:
                csv_writer.writerow(entry.values())

            # Ensure the content is returned as a string
            csv_buffer.seek(0)
            return csv_buffer.getvalue()

        # Get the CSV data and create a Flask response
        csv_data = generate_csv()

        # Prepare the response as a downloadable file
        response = Response(csv_data)
        response.headers['Content-Type'] = 'text/csv'  # Set MIME type to CSV
        response.headers['Content-Disposition'] = 'attachment; filename=vehicles.csv'  # This triggers the download

        return response

    except requests.exceptions.RequestException as e:
        flash(f'Error fetching vehicle data: {str(e)}', 'danger')
        return redirect(url_for('home_blueprint.view_vehicles'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('home_blueprint.view_vehicles'))

@blueprint.route('/drivers/download', methods=['GET'])
@login_required
def download_drivers():
    try:
        # Fetch vehicle data from the external API
        api_response = requests.get(Config.API_URL + '/api/drivers', timeout=10)

        # Check if the response is valid and contains JSON data
        json_data = api_response.json()
        if not json_data:
            flash('No data found to download', 'warning')
            return redirect(url_for('home_blueprint.view_drivers'))
        
        # Generate CSV data to download
        def generate_csv():
            # Create a StringIO buffer to hold CSV data
            csv_buffer = StringIO()
            csv_writer = csv.writer(csv_buffer)

            # Write the header (keys from the first dictionary item)
            headers = json_data[0].keys()  # Assuming the JSON data is a list of dicts
            csv_writer.writerow(headers)

            # Write the rows (values from each dictionary)
            for entry in json_data:
                csv_writer.writerow(entry.values())

            # Ensure the content is returned as a string
            csv_buffer.seek(0)
            return csv_buffer.getvalue()

        # Get the CSV data and create a Flask response
        csv_data = generate_csv()

        # Prepare the response as a downloadable file
        response = Response(csv_data)
        response.headers['Content-Type'] = 'text/csv'  # Set MIME type to CSV
        response.headers['Content-Disposition'] = 'attachment; filename=drivers.csv'  # This triggers the download

        return response

    except requests.exceptions.RequestException as e:
        flash(f'Error fetching driver data: {str(e)}', 'danger')
        return redirect(url_for('home_blueprint.view_drivers'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('home_blueprint.view_drivers'))

@blueprint.route('/drivers', methods=['GET'])
@login_required
def view_drivers():
    try:
        # Get query parameters for pagination (default to page 1, 10 per page)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Fetch drivers from the API
        responses = requests.get(Config.API_URL + '/api/drivers', timeout=10)
        drivers = responses.json()
        
        # Total records and pages
        total_records = len(drivers)
        total_pages = (total_records + per_page - 1) // per_page
        
        # Slice the data based on pagination
        start = (page - 1) * per_page
        end = start + per_page
        drivers_paginated = drivers[start:end]
        
        return render_template(
            "home/tbl_drivers.html",
            drivers=drivers_paginated,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            total_records=total_records,
            start_record=start + 1,
            end_record=min(end, total_records)
        )
    
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)})

# @blueprint.route('/trips', methods=['GET'])
# @login_required
# def view_trips():
#     try:
#         # Get pagination parameters
#         page = request.args.get('page', 1, type=int)
#         per_page = request.args.get('per_page', 10, type=int)
        
#         # Fetch trips, vehicles, and drivers data
#         trips = requests.get(Config.API_URL + '/api/trips', timeout=10).json()
#         vehicles = {v['id']: v['regn_no'] for v in requests.get(Config.API_URL + '/api/vehicles', timeout=10).json()}
#         drivers = {d['id']: d['name'] for d in requests.get(Config.API_URL + '/api/drivers', timeout=10).json()}
        
#         # Update trip details using lookup
#         for trip in trips:
#             trip['vehicle_id'] = vehicles.get(trip['vehicle_id'], 'Unknown')
#             trip['driver_id'] = drivers.get(trip['driver_id'], 'Unknown')

#         # Pagination logic
#         total_records = len(trips)
#         total_pages = (total_records + per_page - 1) // per_page
#         start_record = (page - 1) * per_page
#         end_record = min(start_record + per_page, total_records)

#         # Slice the data for the current page
#         paginated_trips = trips[start_record:end_record]

#         return render_template(
#             "home/tbl_trips.html",
#             trips=paginated_trips,
#             page=page,
#             per_page=per_page,
#             total_pages=total_pages,
#             total_records=total_records,
#             start_record=start_record + 1,
#             end_record=end_record
#         )
    
#     except requests.exceptions.RequestException as e:
#         return jsonify({"error": "Failed to fetch data from API", "details": str(e)})

@blueprint.route('/trips/download', methods=['GET'])
@login_required
def download_trips():
    try:
        # Fetch vehicle data from the external API
        api_response = requests.get(Config.API_URL + '/api/trips', timeout=10)

        # Check if the response is valid and contains JSON data
        json_data = api_response.json()
        if not json_data:
            flash('No data found to download', 'warning')
            return redirect(url_for('home_blueprint.view_trips'))
        
        # Generate CSV data to download
        def generate_csv():
            # Create a StringIO buffer to hold CSV data
            csv_buffer = StringIO()
            csv_writer = csv.writer(csv_buffer)

            # Write the header (keys from the first dictionary item)
            headers = json_data[0].keys()  # Assuming the JSON data is a list of dicts
            csv_writer.writerow(headers)

            # Write the rows (values from each dictionary)
            for entry in json_data:
                csv_writer.writerow(entry.values())

            # Ensure the content is returned as a string
            csv_buffer.seek(0)
            return csv_buffer.getvalue()

        # Get the CSV data and create a Flask response
        csv_data = generate_csv()

        # Prepare the response as a downloadable file
        response = Response(csv_data)
        response.headers['Content-Type'] = 'text/csv'  # Set MIME type to CSV
        response.headers['Content-Disposition'] = 'attachment; filename=trips.csv'  # This triggers the download

        return response

    except requests.exceptions.RequestException as e:
        flash(f'Error fetching trip data: {str(e)}', 'danger')
        return redirect(url_for('home_blueprint.view_trips'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('home_blueprint.view_trips'))

@blueprint.route('/trips', methods=['GET'])
@login_required
def view_trips():
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        # Get date filter parameters
        start_date_str = request.args.get('start_date', None)
        end_date_str = request.args.get('end_date', None)
        IST_OFFSET = timedelta(hours=5, minutes=30)  # IST is UTC+5:30

        # Convert user input date to UTC timestamps (if provided)
        start_date_utc = None
        end_date_utc = None

        if start_date_str:
            try:
                start_date_utc = parse(start_date_str).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
            except ValueError:
                print(f"Invalid start date format: {start_date_str}")

        if end_date_str:
            try:
                end_date_utc = parse(end_date_str).replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(timezone.utc)
            except ValueError:
                print(f"Invalid end date format: {end_date_str}")

        # Fetch trips, vehicles, and drivers data
        trips = requests.get(Config.API_URL + '/api/trips', timeout=10).json()
        vehicles = {v['id']: v['regn_no'] for v in requests.get(Config.API_URL + '/api/vehicles', timeout=10).json()}
        drivers = {d['id']: d['name'] for d in requests.get(Config.API_URL + '/api/drivers', timeout=10).json()}

        # Filter trips based on UTC dates
        filtered_trips = []
        for trip in trips:
            try:
                trip_starttime = parsedate_to_datetime(trip['starttime'])  # Convert API date string to datetime
                
                # Convert IST to UTC
                trip_starttime = trip_starttime - IST_OFFSET  

                # Ensure timezone-aware datetime
                if trip_starttime.tzinfo is None:
                    trip_starttime = trip_starttime.replace(tzinfo=timezone.utc)

                # Apply filters in UTC
                if (not start_date_utc or trip_starttime >= start_date_utc) and (not end_date_utc or trip_starttime <= end_date_utc):
                    trip['vehicle_id'] = vehicles.get(trip['vehicle_id'], 'Unknown')
                    trip['driver_id'] = drivers.get(trip['driver_id'], 'Unknown')
                    filtered_trips.append(trip)

            except Exception as e:
                print(f"Error parsing date: {trip['starttime']} - {e}")

        # Pagination logic
        total_records = len(filtered_trips)
        total_pages = (total_records + per_page - 1) // per_page
        start_record = (page - 1) * per_page
        end_record = min(start_record + per_page, total_records)

        # Slice the data for the current page
        paginated_trips = filtered_trips[start_record:end_record]

        return render_template(
            "home/tbl_trips.html",
            trips=paginated_trips,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            total_records=total_records,
            start_record=start_record + 1,
            end_record=end_record,
            start_date=start_date_str or '',  # Pass back the original string for UI
            end_date=end_date_str or ''       # Pass back the original string for UI
        )

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)})
    
@blueprint.route('/fuellogs/download', methods=['GET'])
@login_required
def download_refills():
    try:
        # Fetch vehicle data from the external API
        api_response = requests.get(Config.API_URL + '/api/fuel_refills', timeout=10)

        # Check if the response is valid and contains JSON data
        json_data = api_response.json()
        if not json_data:
            flash('No data found to download', 'warning')
            return redirect(url_for('home_blueprint.view_trips'))
        
        # Generate CSV data to download
        def generate_csv():
            # Create a StringIO buffer to hold CSV data
            csv_buffer = StringIO()
            csv_writer = csv.writer(csv_buffer)

            # Write the header (keys from the first dictionary item)
            headers = json_data[0].keys()  # Assuming the JSON data is a list of dicts
            csv_writer.writerow(headers)

            # Write the rows (values from each dictionary)
            for entry in json_data:
                csv_writer.writerow(entry.values())

            # Ensure the content is returned as a string
            csv_buffer.seek(0)
            return csv_buffer.getvalue()

        # Get the CSV data and create a Flask response
        csv_data = generate_csv()

        # Prepare the response as a downloadable file
        response = Response(csv_data)
        response.headers['Content-Type'] = 'text/csv'  # Set MIME type to CSV
        response.headers['Content-Disposition'] = 'attachment; filename=fuellogs.csv'  # This triggers the download

        return response

    except requests.exceptions.RequestException as e:
        flash(f'Error fetching fuel data: {str(e)}', 'danger')
        return redirect(url_for('home_blueprint.view_refills'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('home_blueprint.view_refills'))

@blueprint.route('/fuellogs', methods=['GET'])
@login_required
def view_refills():
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        # Get date filter parameters
        start_date_str = request.args.get('start_date', None)
        end_date_str = request.args.get('end_date', None)
        IST_OFFSET = timedelta(hours=5, minutes=30)  # IST is UTC+5:30

        # Convert user input date to UTC timestamps (if provided)
        start_date_utc = None
        end_date_utc = None

        if start_date_str:
            try:
                start_date_utc = parse(start_date_str).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
            except ValueError:
                print(f"Invalid start date format: {start_date_str}")

        if end_date_str:
            try:
                end_date_utc = parse(end_date_str).replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(timezone.utc)
            except ValueError:
                print(f"Invalid end date format: {end_date_str}")
                
        # Fetch fuel refills, vehicles, and drivers data
        fuel_refills_response = requests.get(Config.API_URL + '/api/fuel_refills', timeout=10)
        vehicles_response = requests.get(Config.API_URL + '/api/vehicles', timeout=10)
        drivers_response = requests.get(Config.API_URL + '/api/drivers', timeout=10)
        # Check for successful response from the API
        if fuel_refills_response.status_code != 200:
            print(f"Error fetching fuel refills: {fuel_refills_response.status_code} - {fuel_refills_response.text}")
            return jsonify({"error": "Failed to fetch fuel refills data from API", "details": fuel_refills_response.text})
        
        if vehicles_response.status_code != 200:
            print(f"Error fetching vehicles: {vehicles_response.status_code} - {vehicles_response.text}")
            return jsonify({"error": "Failed to fetch vehicles data from API", "details": vehicles_response.text})
        
        if drivers_response.status_code != 200:
            print(f"Error fetching drivers: {drivers_response.status_code} - {drivers_response.text}")
            return jsonify({"error": "Failed to fetch drivers data from API", "details": drivers_response.text})
        # Parse the JSON responses
        fuel_refills = fuel_refills_response.json()
        vehicles = {v['id']: v['regn_no'] for v in vehicles_response.json()}
        drivers = {d['id']: d['name'] for d in drivers_response.json()}
        # If no data found, render a message indicating no records
        if not fuel_refills or not vehicles or not drivers:
            return render_template(
                "home/tbl_fuel_logs.html",
                fuel_logs=[],
                page=page,
                per_page=per_page,
                total_pages=0,
                total_records=0,
                start_record=0,
                end_record=0,
                start_date=start_date_str or '',
                end_date=end_date_str or '',
                no_data_found=True  # Flag for UI to show a "No data found" message
            )
        # Filter fuel refills based on UTC dates
        filtered_refills = []
        for refill in fuel_refills:
            try:
                print(f"Raw time string: {refill.get('time')}")
                print(refill['time'])
                refill_time = parsedate_to_datetime(refill['time'])  # Convert API date string to datetime

                # Convert IST to UTC (subtract 5:30 hours)
                refill_time = refill_time - IST_OFFSET

                # Ensure refill_time is timezone-aware
                if refill_time.tzinfo is None:
                    refill_time = refill_time.replace(tzinfo=timezone.utc)

                # Apply filters in UTC
                if (not start_date_utc or refill_time >= start_date_utc) and (not end_date_utc or refill_time <= end_date_utc):
                    refill['vehicle_id'] = vehicles.get(refill['vehicle_id'], 'Unknown')
                    refill['driver_id'] = drivers.get(refill['driver_id'], 'Unknown')
                    filtered_refills.append(refill)

            except Exception as e:
                print(f"Error parsing date: {refill['time']} - {e}")

        # If no filtered refills found, render a message indicating no data
        if not filtered_refills:
            return render_template(
                "home/tbl_fuellogs.html",
                fuel_logs=[],
                page=page,
                per_page=per_page,
                total_pages=0,
                total_records=0,
                start_record=0,
                end_record=0,
                start_date=start_date_str or '',
                end_date=end_date_str or '',
                no_data_found=True  # Flag for UI to show a "No data found" message
            )

        # Pagination logic
        total_records = len(filtered_refills)
        total_pages = (total_records + per_page - 1) // per_page
        start_record = (page - 1) * per_page
        end_record = min(start_record + per_page, total_records)

        # Slice the data for the current page
        paginated_refills = filtered_refills[start_record:end_record]

        return render_template(
            "home/tbl_fuellogs.html",
            fuel_logs=paginated_refills,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            total_records=total_records,
            start_record=start_record + 1,
            end_record=end_record,
            start_date=start_date_str or '',  # Pass back the original string for UI
            end_date=end_date_str or '',      # Pass back the original string for UI
            no_data_found=False  # Set this to False when there is data
        )

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)})
    except Exception as e:
        print(f"Unexpected error: {e}")
        return redirect(url_for('home_blueprint.view_refills'))
    
# @blueprint.route('/fuellogs', methods=['GET'])
# @login_required
# def view_refills():
#     try:
#         responses = requests.get(Config.API_URL+'/api/fuel_refills', timeout=10)
#         fuellogs = responses.json()
#         print(fuellogs)
    
#         if isinstance(fuellogs, list):
#             for fuellog in fuellogs:
#                 vehicle = requests.get(Config.API_URL+'/api/vehicles/'+str(fuellog['vehicle_id']), timeout=10).json()
#                 fuellog['vehicle_id'] = vehicle['regn_no']
#                 driver = requests.get(Config.API_URL+'/api/drivers/'+str(fuellog['driver_id']), timeout=10).json()
#                 fuellog['driver_id'] = driver['name']
#                 # card = requests.get(Config.API_URL+'/api/cards/'+str(fuellog['card_id']), timeout=10).json()
#                 # fuellog['card_id'] = card['card_no']
            
#         return render_template("home/tbl_fuellogs.html", fuellogs=fuellogs)    
#     except requests.exceptions.RequestException as e:
#         return jsonify({"error": "Failed to fetch data from API", "details": str(e)})

    
@blueprint.route('/drivers/add', methods=['POST'])
@login_required
def add_driver():
    # Get form data
    name = request.form.get('name')
    mobile = request.form.get('mobile')
    dl_number = request.form.get('dl_number')
    password = request.form.get('password')

    # Prepare driver data
    data = {
        "name": name,
        "mobile": mobile,
        "dl_number": dl_number,
        "is_approved": False,
        "password": password,
    }

    # Handle multiple file uploads
    uploaded_files = request.files.getlist('files')  # Get multiple files
    files = []
    
    if uploaded_files:
        try:
            for file in uploaded_files:
                if file and file.filename:  # Ensure file is not empty
                    filename = secure_filename(file.filename)
                    files.append(('files', (filename, file, file.content_type)))  # Append each file
        except Exception as e:
            flash(f"Error uploading files: {str(e)}", "danger")
            return redirect(url_for('home_blueprint.view_drivers'))
    else:
        flash("No files uploaded", "danger")
        return redirect(url_for('home_blueprint.view_drivers'))  # Redirect if no files uploaded

    # Send the request with multiple files
    try:
        response = requests.post(Config.API_URL + '/api/drivers/register', data=data, files=files, timeout=10)
        
        if response.status_code == 200:

            return redirect(url_for('home_blueprint.view_drivers'))
        
        else:
            flash(f"Error: {response.json()}", "danger")
            return redirect(url_for('home_blueprint.view_drivers'))
        
    except requests.exceptions.RequestException as e:
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for('home_blueprint.view_drivers'))  # Redirect to updated list

# Route to add a driver
# @blueprint.route('/drivers/add', methods=['POST'])
# @login_required
# def add_driver():
#     # Get form data
#     name = request.form.get('name')
#     mobile = request.form.get('mobile')
#     dl_number = request.form.get('dl_number')
#     is_approved = request.form.get('is_approved')
#     files = request.files.get('files')
#     password = request.form.get('password')

#     # Validate password
#     if not password or len(password) != 4 or not password.isdigit():
#         password = generate_password()
#     else:
#         password = password

#     # Prepare driver data
#     data = {
#         "name": name,
#         "mobile": mobile,
#         "dl_number": dl_number,
#         "is_approved": True if is_approved == "Yes" else False,
#         "password": password,
#     }
#     if files:
#         # Secure the filename to prevent security issues
#         try:
#             filename = secure_filename(files.filename)
#             # print(filename)
#             files = {
#                 'files': (filename, files, files.content_type)
#             }
#         except Exception as e:
#             flash(f"Error uploading file: {str(e)}", "danger")
#             return redirect(url_for('home_blueprint.view_drivers'))
#     else:
#         flash("No image uploaded", "danger")
#         return redirect(url_for('home_blueprint.view_drivers'))  # Redirect to updated list if no file
    
#     try:
#         response = requests.post(Config.API_URL + '/api/drivers/register', data=data, files=files, timeout=10)
#         if response.status_code == 200:
#             # response_data = response.json()
#             # print(response_data)
#             return redirect(url_for('home_blueprint.view_drivers'))
#         else:
#             print(response.status_code)
#             print(f"Error: {response.json()}", response.status_code)
#             return redirect(url_for('home_blueprint.view_drivers'))
        
#     except requests.exceptions.RequestException as e:
#         flash(f"Error: {str(e)}", "danger")

#     return redirect(url_for('home_blueprint.view_drivers'))  # Redirect to updated list

@blueprint.route('/drivers/update/<int:id>', methods=['POST'])
@login_required
def update_driver(id):
    name = request.form.get('name')
    mobile = request.form.get('mobile')
    dl_number = request.form.get('dl_number')
    is_approved = request.form.get('is_approved')
    
    if(is_approved=="Yes"):
        is_approved = "true"
    else:
        is_approved = "false"
    password = request.form.get('password')
    if not password or len(password) != 4 or not password.isdigit():
        password = generate_password()
    else:
        password = password
    uploaded_files = request.files.getlist('files')  # Get multiple files
    files = []
    if uploaded_files:
        try:
            for file in uploaded_files:
                if file and file.filename:  # Ensure file is not empty
                    filename = secure_filename(file.filename)
                    files.append(('files', (filename, file, file.content_type)))  # Append each file
        except Exception as e:
            flash(f"Error uploading files: {str(e)}", "danger")
            return redirect(url_for('home_blueprint.view_drivers'))
    else:
        flash("No files uploaded", "danger")
        return redirect(url_for('home_blueprint.view_drivers'))  # Redirect if no files uploaded



    data = {
    "id":id,   
    "name": name,
    "mobile": mobile,
    "dl_number": dl_number,
    "dl_image": filename if files else dl_image,
    "is_approved": is_approved,
    "password": int(password)
    }
    # print(data)
    try:
        # print(Config.API_URL + '/api/drivers/update/'+str(id))
        # print(data)
        response = requests.post(Config.API_URL + '/api/drivers/update/'+str(id), data=data, files = files, timeout=10)
        response.raise_for_status()  # Raise error for non-2xx responses
        flash("Driver updated successfully!", "success")
    except requests.exceptions.RequestException as e:
        flash(f"Error: {str(e)}", "danger")

    # return jsonify(response.text)
    return redirect(url_for('home_blueprint.view_drivers'))  # Redirect to updated list


@blueprint.route('/drivers/edit/<int:id>', methods=['GET'])
@login_required
def edit_driver(id):
    try:
        response = requests.get(Config.API_URL+'/api/drivers/'+str(id), timeout=10)
        driver = response.json()
        # print(driver)
        return render_template("home/edit_driver.html", driver=driver)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)})

@blueprint.route('/drivers/approve/<int:id>', methods=['POST'])
@login_required
def approve_driver(id):
    try:

        response = requests.post(Config.API_URL + '/api/drivers/approve/' + str(id), timeout=10)
        if response.status_code == 200:
            flash("Driver approved successfully!", "success")
        else:
            flash("Error approving driver. Please try again.")

    except Exception as e:
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for('home_blueprint.view_drivers'))

@blueprint.route('/drivers/delete/<int:id>', methods=['POST'])
@login_required
def delete_driver(id):
    # print(id)
    try:
        response = requests.post(Config.API_URL + '/api/drivers/delete/' + str(id), timeout=10)
        
        if response.status_code == 200:
            flash("Driver deleted successfully!", "success")
        else:
            flash("Error deleting driver. Please try again.", "danger")
            
    except requests.exceptions.RequestException as e:
        flash(f"Error: {str(e)}", "danger")
    
    return redirect(url_for('home_blueprint.view_drivers'))

# Helper - Extract current page name from request
@blueprint.route('/cards/edit/<int:id>', methods=['GET'])
@login_required
def edit_card(id):
    try:
        response = requests.get(Config.API_URL+'/api/cards/'+str(id), timeout=10)
        card = response.json()
        return render_template("home/edit_card.html", card=card)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)})

@blueprint.route('/cards/delete/<int:id>', methods=['POST'])
@login_required
def delete_card(id):
    try:
        response = requests.post(Config.API_URL + '/api/cards/delete/' + str(id), timeout=10)
        
        if response.status_code == 200:
            flash("Card deleted successfully!", "success")
        else:
            flash("Error deleting driver. Please try again.", "danger")
            
    except requests.exceptions.RequestException as e:
        flash(f"Error: {str(e)}", "danger")
    
    return redirect(url_for('home_blueprint.view_cards'))

# Helper - Extract current page name from request
@blueprint.route('/cards/update/<int:id>', methods=['POST'])
@login_required
def update_card(id):
    card_no = request.form.get('card_no')
    assigned_to = request.form.get('assigned_to')
    company = request.form.get('company')
    
    data = {
    "id":id,   
    "card_no": card_no,
    "assigned_to": assigned_to,
    "company": company
    }
    try:
        response = requests.post(Config.API_URL + '/api/cards/update/'+str(id), json=data, timeout=10)
        response.raise_for_status()  # Raise error for non-2xx responses
        flash("Card updated successfully!", "success")
    except requests.exceptions.RequestException as e:
        flash(f"Error: {str(e)}", "danger")

    # return jsonify(response.text)
    return redirect(url_for('home_blueprint.view_cards'))  # Redirect to updated list

# @blueprint.route('/cards', methods=['GET'])
# @login_required
# def view_cards():
#     try:
#         responses = requests.get(Config.API_URL+'/api/cards', timeout=10)
#         cards = responses.json()
#         return render_template("home/tbl_cards.html", cards=cards)
    
#     except requests.exceptions.RequestException as e:
#         return jsonify({"error": "Failed to fetch data from API", "details": str(e)})
@blueprint.route('/cards/download', methods=['GET'])
@login_required
def download_cards():
    try:
        # Fetch vehicle data from the external API
        api_response = requests.get(Config.API_URL + '/api/cards', timeout=10)

        # Check if the response is valid and contains JSON data
        json_data = api_response.json()
        if not json_data:
            flash('No data found to download', 'warning')
            return redirect(url_for('home_blueprint.view_cards'))
        
        # Generate CSV data to download
        def generate_csv():
            # Create a StringIO buffer to hold CSV data
            csv_buffer = StringIO()
            csv_writer = csv.writer(csv_buffer)

            # Write the header (keys from the first dictionary item)
            headers = json_data[0].keys()  # Assuming the JSON data is a list of dicts
            csv_writer.writerow(headers)

            # Write the rows (values from each dictionary)
            for entry in json_data:
                csv_writer.writerow(entry.values())

            # Ensure the content is returned as a string
            csv_buffer.seek(0)
            return csv_buffer.getvalue()

        # Get the CSV data and create a Flask response
        csv_data = generate_csv()

        # Prepare the response as a downloadable file
        response = Response(csv_data)
        response.headers['Content-Type'] = 'text/csv'  # Set MIME type to CSV
        response.headers['Content-Disposition'] = 'attachment; filename=cards.csv'  # This triggers the download

        return response

    except requests.exceptions.RequestException as e:
        flash(f'Error fetching vehicle data: {str(e)}', 'danger')
        return redirect(url_for('home_blueprint.view_vehicles'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('home_blueprint.view_vehicles'))


@blueprint.route('/cards', methods=['GET'])
@login_required
def view_cards():
    try:
        page = request.args.get('page', 1)
        per_page = request.args.get('per_page', 10)  # Allow dynamic rows per page
        
        # Validate page and per_page
        if not str(page).isdigit() or int(page) <= 0:
            page = 1
        if not str(per_page).isdigit() or int(per_page) <= 0:
            per_page = 10
        
        page = int(page)
        per_page = int(per_page)

        response = requests.get(Config.API_URL + '/api/cards', timeout=10)
        response.raise_for_status()
        cards = response.json()

        total_records = len(cards)
        total_pages = math.ceil(total_records / per_page)

        # Paginate cards
        start = (page - 1) * per_page
        end = min(start + per_page, total_records)
        paginated_cards = cards[start:end]

        return render_template(
            "home/tbl_cards.html",
            allCards = cards,
            cards=paginated_cards,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            total_records=total_records,
            start_record=start + 1 if total_records > 0 else 0,
            end_record=end if total_records > 0 else 0
        )

    except requests.exceptions.HTTPError as e:
        return jsonify({"error": "HTTP error occurred", "details": str(e)}), 500
    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)}), 500
    except ValueError:
        return jsonify({"error": "Invalid JSON response from API"}), 500


@blueprint.route('/cards/add', methods=['POST'])
@login_required
def add_card():
    
    card_no = request.form.get('card_no')
    company = request.form.get('company')
    assigned_to = request.form.get('assigned_to')
 
    if not card_no or not company or not assigned_to:
        flash("All fields are required.", "warning")
        return redirect(url_for('home_blueprint.view_cards'))

    data = {
        "card_no": card_no,
        "company": company,
        "assigned_to": assigned_to,
    }
    try:
        response = requests.post(Config.API_URL + '/api/cards/add', json=data, timeout=10)
        response.raise_for_status()  # Raise error for non-2xx responses
        flash("Card added successfully!", "success")
    except requests.exceptions.RequestException as e:
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for('home_blueprint.view_cards'))  # Redirect to updated list

@blueprint.route('/drivers/pending', methods=['GET'])
@login_required
def pending_drivers():
    try:
        responses = requests.get(Config.API_URL+'/api/drivers/pending', timeout=10)
        if responses:
            pending_drivers = responses.json()
        else:
            pending_drivers = 0
        print(pending_drivers)
        return dict(pending_drivers=pending_drivers)
    
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)})

def driver_performance():
    try:
        responses = requests.get(Config.API_URL + '/api/fuel_refills/driver_performance', timeout=10)
        
        # Check if the response is successful
        if responses.status_code == 200:
            try:
                drivers = responses.json()
            except ValueError:
                return jsonify({"error": "Invalid JSON response from API"}), 500
        else:
            return jsonify({"error": f"API request failed with status {responses.status_code}"}), 500

        return drivers

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)}), 500

def vehicle_performance():
    try:
        responses = requests.get(Config.API_URL + '/api/fuel_refills/vehicle_performance', timeout=10)
        
        # Check if the response is successful
        if responses.status_code == 200:
            try:
                vehicles = responses.json()
            except ValueError:
                return jsonify({"error": "Invalid JSON response from API"}), 500
        else:
            return jsonify({"error": f"API request failed with status {responses.status_code}"}), 500

        return vehicles

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch data from API", "details": str(e)}), 500

def get_segment(request):

    try:
    # Extract the segment from the URL path
        segment = request.path.strip('/')

    # Remove .html extension if present
        if segment.endswith('.html'):
            segment = segment[:-5]  # Remove the last 5 characters (.html)
        return segment
    
    except:
        return None
