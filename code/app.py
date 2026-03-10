import datetime
from enum import Enum
import os
import re
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, flash, redirect, request, send_from_directory, url_for, render_template,session
from sqlalchemy import Column, ForeignKey, Integer
from werkzeug.security import check_password_hash, generate_password_hash
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from datetime import datetime
from sqlalchemy import or_
from sqlalchemy import func
from werkzeug.utils import secure_filename


db = SQLAlchemy()

migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = "login"  

class StatusEnum(Enum):
    Pending = "Pending"
    In_progress = "In_progress"
    Completed = "Completed"
    Rejected = "Rejected"
    Cancelled = "Cancelled"
    Accepted = "Accepted"
    Approved = "Approved"

class Rating(db.Model,UserMixin):
    __tablename__ = 'rating'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    professional_id = db.Column(db.Integer, db.ForeignKey('service_professional.id'), nullable=False)
    service_request_id = db.Column(db.Integer, db.ForeignKey('service_request.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  
    comment = db.Column(db.String(500), nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', backref='ratings')
    professional = db.relationship('ServiceProfessional', backref='ratings')
    service_request = db.relationship('ServiceRequest', backref='ratings')

class Admin(db.Model, UserMixin):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    adminname = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)

    def __repr__(self):
        return f"<Admin {self.adminname}>"

class Customer(db.Model, UserMixin):
    __tablename__ = 'customer'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    pincode = db.Column(db.Integer, nullable=True)
    address = db.Column(db.String(150), nullable=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    mobile = db.Column(db.String(15), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    block = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Customer {self.username}>"

class ServiceProfessional(db.Model, UserMixin):
    __tablename__ = 'service_professional'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    mobile = db.Column(db.String(15), nullable=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    servicename = db.Column(db.String(150), nullable=False)
    experience = db.Column(db.Integer, default=0)
    Approve = db.Column(db.Boolean, default=False)
    block = db.Column(db.Boolean, default=False) 

    packages = db.relationship("Package", back_populates="service_professional")
    services = db.relationship('Service', back_populates='service_professional', lazy='joined')

    def __repr__(self):
        return f"<ServiceProfessional {self.username}>"

class Service(db.Model, UserMixin):
    __tablename__ = 'service'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    price = db.Column(db.Float, nullable=False)
    time_required = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    servicename = db.Column(db.String(150), db.ForeignKey('service_professional.servicename'), nullable=False)

    service_professional = db.relationship('ServiceProfessional', back_populates='services')
    packages = db.relationship('Package', back_populates='service', lazy='joined')

    def __repr__(self):
        return f"<Service {self.servicename} - ${self.price}>"

class Package(db.Model,UserMixin):
    __tablename__ = 'packages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    service_professional_id = db.Column(db.Integer, db.ForeignKey('service_professional.id'), nullable=True)

    service = db.relationship('Service', back_populates='packages')
    service_professional = db.relationship("ServiceProfessional", back_populates="packages")
    service_requests = db.relationship('ServiceRequest', backref='package', lazy=True)

    def __repr__(self):
        return f"<Package {self.name} - ${self.price}>"

class ServiceRequest(db.Model,UserMixin):
    __tablename__ = 'service_request'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    date_of_request = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    date_of_completion = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.Enum(StatusEnum), nullable=False, default=StatusEnum.Pending)
    remarks = db.Column(db.String(500), nullable=True)
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'), nullable=True)
    professional_id = db.Column(db.Integer, db.ForeignKey('service_professional.id'), nullable=True)

    customer = db.relationship('Customer', backref=db.backref('customer_requests', lazy=True))
    service = db.relationship('Service', backref=db.backref('service_requests', lazy=True))
    professional = db.relationship('ServiceProfessional', backref='service_requests')

    def __repr__(self):
        return f"<ServiceRequest {self.id} - Status: {self.status}>"

def create_app():
    app = Flask(__name__)
    

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mad1household.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'yuvrajmad1projectkey')  # Use environment variable
    
 
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    login_manager.login_view = '/login'
    login_manager.login_message = "Please log in to access this page."


    with app.app_context():
        db.create_all()

    return app

@login_manager.user_loader
def load_user(user_id):

    user = db.session.get(Customer, int(user_id))
    if user:
        return user

    user = db.session.get(Admin, int(user_id))
    if user:
        return user

    user = db.session.get(ServiceProfessional, int(user_id))
    return user  # This will return None if no user is found

# Define routes
def register_routes(app):
    @app.route("/")
    def home():
        return render_template("landing.html")

    @app.route("/login", methods=["GET", "POST"])
    def user_login():
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")

            user = Customer.query.filter_by(username=username).first()

            if (user and check_password_hash(user.password, password)) and (user.block==0):
                login_user(user)
                return redirect(url_for('cushome'))

            return render_template("login.html", msg="Invalid username or password!")

        return render_template("login.html", msg="Invalid username or password!")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('home'))

    @app.route("/dashboard")
    @login_required
    def cushome():
        # Fetch all services for the customer dashboard (if needed)

            user = Customer.query.get(current_user.id)  # Get single customer
            services = Service.query.all()  # Get all services
            requests = ServiceRequest.query.filter_by(customer_id=current_user.id).all()  # Get all requests for this customer
            ratings = Rating.query.all()  # Fetch all existing ratings
            #package=Package.query.all()
            #package=[]
            for request in requests:
                request.pkg_name = Package.query.get(request.package_id).name if request.package_id else None

            return render_template('Customer_dashboard.html', 
                                user=current_user,
                                services=services,
                                Requests=requests,
                                ratings=ratings)


    @app.route("/register", methods=["GET", "POST"])
    def CustomerSignup():
        if request.method == "POST":
            email = request.form.get('email')
            mobile = request.form.get('mobile')
            name = request.form.get('name')
            address = request.form.get('address')
            pincode = request.form.get('pincode')
            username = request.form.get('username')
            password = request.form.get('password')

            if not all([username, password, email, name, address, pincode, mobile]):
                return render_template("CustomerSignup.html", msg="Please provide all required fields!")

            usr = Customer.query.filter(
                (Customer.username == username) | (Customer.email == email)
            ).first()

            if usr:
                return render_template("CustomerSignup.html", msg="Username or email already exists!")

            hashed_password = generate_password_hash(password)

            try:
                new_user = Customer(
                    email=email,
                    mobile=mobile,
                    name=name,
                    address=address,
                    pincode=pincode,
                    username=username,
                    password=hashed_password
                )
                db.session.add(new_user)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                return render_template("CustomerSignup.html", msg=f"Database error: {str(e)}")

            return render_template("login.html", msg="Registration successful! Please log in.")

        return render_template("CustomerSignup.html", msg="")
    @app.route("/registerpro", methods=["GET", "POST"])
    def pro_signup():
        services = Service.query.with_entities(Service.servicename).all()

        if request.method == "POST":
            email = request.form.get('email')
            mobile = request.form.get('mobile')
            name = request.form.get('name')
            username = request.form.get('username')
            servicename = request.form.get('servicename')
            experience = request.form.get('experience')
            password = request.form.get('password')

            # Debug form data
            print(f"Form data: {email}, {name}, {username}, {servicename}, {experience}, {mobile}, {password}")

            # Validate required fields
            if not all([email, name, username, servicename, experience, password]):
                return render_template("pro_signup.html", services=services, msg="Provide all required fields!")

            # Convert experience
            try:
                experience = int(experience)
            except ValueError:
                return render_template("pro_signup.html", services=services, msg="Experience must be a valid number.")

            # Hash password
            try:
                hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            except Exception as e:
                print(f"Password hashing error: {e}")
                return render_template("pro_signup.html", services=services, msg="Error hashing password.")

            # Add to database
            try:
                new_pro = ServiceProfessional(
                    email=email,
                    name=name,
                    username=username,
                    servicename=servicename,
                    experience=experience,
                    mobile=mobile,
                    password=hashed_password
                )
                db.session.add(new_pro)
                db.session.commit()
                print("User added successfully.")
            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Database error: {e}")
                return render_template("pro_signup.html", services=services, msg="An error occurred during registration.")

            # Redirect to login on success
            return render_template("landing.html", msg="Registration successful! Please log in.")

        return render_template("pro_signup.html", services=services, msg="")


    @app.route("/loginpro", methods=["GET", "POST"])
    def pro_login():
        # Redirect if already authenticated
        if current_user.is_authenticated:
            return redirect(url_for('prodash'))

        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")

            pro = ServiceProfessional.query.filter_by(username=username).first()
            if (pro and check_password_hash(pro.password, password)) and (pro.block==0 and pro.Approve==1):
                session.clear()

                logout_user()
                login_user(pro)

                return redirect(url_for('prodash'))

            flash("Invalid username or password or user is blocked!", "error")
            return render_template("loginpro.html", msg="Invalid username or password! or useer is blocked", username=username)

  
        return render_template("loginpro.html", msg="")
    @app.route("/add_request", methods=["GET", "POST"])
    @login_required
    def servicerequest():
        package_id = request.args.get("package_id")

        if request.method == "POST":
            service_id = request.form.get("service_id") 
            customer_id = current_user.id
            status = request.form.get("status") or StatusEnum.Pending.value
            remarks = request.form.get("remarks")
            package_id=request.form.get("package_id")

            # Create a new service request entry
            try:
                new_request = ServiceRequest(
                    service_id=service_id,
                    customer_id=customer_id,
                    professional_id= None,
                    package_id=package_id,
                    status=status,
                    remarks=remarks,
                )
                db.session.add(new_request)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                return render_template("Customer_dashboard.html", msg=f"Database error: {str(e)}", user=current_user)

            return redirect(url_for('cushome'))

        return render_template("Customer_dashboard.html", msg="", package_id=package_id, user=current_user)


    @app.route("/addservice", methods=["GET", "POST"])
    @login_required
    def addservices():
        if request.method == "POST":
            servicename = request.form.get("servicename")
            description = request.form.get("description")
            price = request.form.get("price")
            time_required = request.form.get("time_required")

            
            if not all([servicename, description,price, time_required]):
                return render_template("Admin_dashboard.html", msg="Please provide all required fields")
            
            try:
                
                new_service = Service(
                    servicename=servicename,
                    price=price,
                    time_required=time_required,
                    description=description
                )
                db.session.add(new_service)
                db.session.commit()
                flash("Registration successful! Please log in.", "success")
            except SQLAlchemyError as e:
                db.session.rollback()
                return render_template("Admin_dashboard.html", msg=f"Database error: {str(e)}")
            
           
            return redirect(url_for('adminhome')) 
        
        return render_template("Admin_dashboard.html")



    @app.route("/service")
    def service():
        return render_template("service.html")
    
    @app.route("/adminlogin", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            adminname = request.form.get("adminname")
            password = request.form.get("password")


            admin = Admin.query.filter_by(adminname=adminname).first()


            if admin and password==password:
               
                login_user(admin)
                flash('Logged in successfully.', 'success')
                return redirect(url_for('adminhome'))
           
            return render_template("adminlogin.html", msg="Invalid username or password!")
     
        return render_template("adminlogin.html", msg="")


    @app.route("/admindashboard")
    @login_required
    def adminhome():
        
        services = Service.query.all()
        professionals = ServiceProfessional.query.all()
        customers = Customer.query.all()
        
        requests = (
            ServiceRequest.query
            .join(Service, ServiceRequest.service_id == Service.id)
            .filter(
                or_(
                    ServiceRequest.status == StatusEnum.Pending.value,
                    ServiceRequest.status == StatusEnum.In_progress.value,
                    ServiceRequest.status == StatusEnum.Completed.value,
                    ServiceRequest.status == StatusEnum.Cancelled.value,
                    ServiceRequest.status == StatusEnum.Rejected.value,
                    ServiceRequest.status == StatusEnum.Accepted.value
                )
            )
            .all()
        )

        
        for request in requests:
            
            package = Package.query.get(request.package_id)
            request.pkg_name = package.name if package else "No Package"
            customer = Customer.query.get(request.customer_id)
            request.cus_name = customer.name if customer else "No Customer"
            request.cus_address = customer.address if customer else "No address"
            request.cus_pincode = customer.pincode if customer else "No pincode"
            professional = ServiceProfessional.query.get(request.professional_id)
            request.professional_name = professional.name if professional else "No Professional"

      
        return render_template(
            "Admin_dashboard.html",
            services=services,
            professionals=professionals,
            admin=current_user,
            customers=customers,
            requests=requests
        )


    @app.route("/editservice/<int:service_id>", methods=["GET", "POST"])
    @login_required
    def edit_service(service_id):
        service = Service.query.get_or_404(service_id)
        
        if request.method == "POST":
            servicename = request.form.get("servicename")
            description = request.form.get("description")
            price = request.form.get("price")
            time_required = request.form.get("time_required")

            if not all([servicename, description, price,time_required]):
                return render_template("edit_service.html", service=service, msg="All fields are required.")
            
            try:
                service.servicename = servicename
                service.description = description
                service.price = price
                service.time_required = time_required
                
             
                db.session.commit()
                return redirect(url_for('adminhome')) 
            except SQLAlchemyError as e:
                db.session.rollback()
                return f"An error occurred: {str(e)}"
        
        
        return render_template("edit_service.html", service=service)
    
    @app.route("/deleteservice/<int:service_id>", methods=["GET","POST"])
    @login_required
    def delete_service(service_id):
        service = Service.query.get_or_404(service_id)
        
        try:
            db.session.delete(service)
            db.session.commit()  
            return redirect(url_for('adminhome'))
        except SQLAlchemyError as e:
            db.session.rollback()
            return f"An error occurred: {str(e)}"
    
    @app.route('/package/<int:service_id>',methods=['GET','POST'])
    def package(service_id):
 
        packages= Package.query.filter_by(service_id=service_id).all()
        service = Service.query.get_or_404(service_id)
        # Pass the services data to the template
        return render_template("packages.html",packages=packages,service=service)

    @app.route('/adminpackage/<int:service_id>',methods=['GET','POST'])
    def adminpackage(service_id):
        services=Service.query.all()
        return render_template("packages.html",services=services)
    @app.route('/newpackage', methods=['GET', 'POST'])
    def add_package():
        if request.method == 'POST':
            
            name = request.form['name']
            details = request.form['details']
            price = request.form['price']
            service_id = request.form['service_id']
            
            
            if not all([name,details,service_id]):
                flash('Please fill in all required fields','danger')
                return redirect(url_for('add_package'))
            
            try:
                
                service_id=int(service_id)
                service= Service.query.get(service_id)
                if not service:
                    flash('Invalid service seleted','danger')
                    return redirect(url_for('add_package'))
                

                new_package = Package(
                    name=name,
                    details=details,
                    price=price,
                    service_id=service_id
                )
                
                
                db.session.add(new_package)
                db.session.commit()
                
                flash('Package added successfully!', 'success')
                return redirect(url_for('adminhome'))
            
            except ValueError:
                flash('Invalid service ID', 'danger')
                return redirect(url_for('add_package'))
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f'Error adding package: {str(e)}', 'danger')
                return redirect(url_for('add_package'))
        
       
        services = Service.query.all()  
        return render_template('packages.html', services=services)
    
    @app.route("/adminseepackage/<int:service_id>", methods=['GET', 'POST'])
    def admin_SEEpackage(service_id):
        packages = Package.query.filter_by(service_id=service_id).all()
        return render_template('admin_SEEpackage.html', packages=packages,service_id=service_id)
    
    @app.route('/cuspackages/<int:service_id>', methods=['GET',"POST"])
    def cuspackages(service_id):
        professionals = ServiceProfessional.query.all()
       
        packages = Package.query.filter_by(service_id=service_id).all()
        service=Service.query.get_or_404(service_id)
       
        return render_template("cus_pack.html", packages=packages,service=service)
    
    @app.route("/delete_request/<int:request_id>", methods=["GET","POST"])
    @login_required
    def delete_request(request_id):
        service_request = ServiceRequest.query.get_or_404(request_id)
        
        try:
            db.session.delete(service_request)
            db.session.commit()
            flash('Request deleted successfully!', 'success')
            return redirect(url_for('cushome'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error deleting request: {str(e)}', 'error')
            return redirect(url_for('cushome'))
    @app.route("/rcusprofile", methods=["GET", "POST"])
    @login_required
    def fcusprofile():
        return render_template("cusprofile.html", user=current_user)
    
    @app.route("/rcusprofileedit",methods=["GET","POST"])
    @login_required
    def fcusprofileedit():
        return render_template("cusprofile_edit.html", user=current_user)
    @app.route("/cusupdateprofile",methods=["GET","POST"])
    @login_required
    def fcusprofileupdate():
        if request.method == "POST":
            
            email = request.form.get('email')
            mobile = request.form.get('mobile')
            name = request.form.get('name')
            address = request.form.get('address')
            pincode = request.form.get('pincode')
            username = request.form.get('username')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            
            if not all([username, email, name, address, pincode, mobile]):
                return render_template("Customer_dashboard.html", msg="Please provide all required fields!")

            
            if password and password != confirm_password:
                return render_template("Customer_dashboard.html", msg="Passwords do not match!")

            
            existing_user = Customer.query.filter(
                (Customer.username == username) | (Customer.email == email),
                Customer.id != current_user.id
            ).first()
            
            if existing_user:
                return render_template("Customer_dashboard.html", msg="Username or email already exists!")

           
            current_user.email = email
            current_user.mobile = mobile
            current_user.name = name
            current_user.address = address
            current_user.pincode = pincode
            current_user.username = username
            if password:
                current_user.password = generate_password_hash(password)

            try:
                db.session.commit()
                flash("Profile updated successfully!", "success")
                return redirect(url_for("cushome"))
            except SQLAlchemyError as e:
                db.session.rollback()
                return render_template("Customer_dashboard.html", msg=f"Database error: {str(e)}")

        return render_template("profile.html", user=current_user)
    
    @app.route("/rproprofile", methods=["GET", "POST"])
    @login_required
    def fproprofile():
        pro=ServiceProfessional.query.get(current_user.id)
        return render_template("proprofile.html", pro=pro)
    
    @app.route("/rproprofileedit",methods=["GET","POST"])
    @login_required
    def fproprofileedit():
        pro=ServiceProfessional.query.get(current_user.id)
        services=Service.query.all()
        return render_template("proprofile_edit.html", pro=pro,services=services)
    
    @app.route("/rproupdateprofile", methods=["GET", "POST"])
    @login_required
    def fproprofileupdate():
        pro=ServiceProfessional.query.get(current_user.id)
        if request.method == "POST":
           
            email = request.form.get('email')
            mobile = request.form.get('mobile')
            name = request.form.get('name')
            username = request.form.get('username')
            servicename = request.form.get('servicename')
            experience = request.form.get('experience')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            
            if not all([username, email, name, servicename, mobile,experience]):
                return render_template("professional_dashboard.html", msg="Please provide all required fields!")

            
            if password and password != confirm_password:
                return render_template("professional_dashboard.html", msg="Passwords do not match!")

            
            existing_user = ServiceProfessional.query.filter(
                ServiceProfessional.username == username,
                ServiceProfessional.id != current_user.id
            ).first()
            
            if existing_user:
                return render_template("professional_dashboard.html", msg="Username already exists!")

            try:
                
                pro.email = email
                pro.mobile = mobile
                pro.name = name
                pro.servicename = servicename
                pro.username = username
                pro.experience = experience
                
                if password:
                    pro.password = generate_password_hash(password)

               
                db.session.commit()

                flash("Profile updated successfully!", "success")
                return redirect(url_for("prodash"))

            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.error(f"Database error during profile update: {str(e)}")
                return render_template("professional_dashboard.html", msg="An error occurred while updating your profile. Please try again.")

        
        return render_template("proprofile.html", pro=pro)


    @app.route('/search_packages', methods=['GET', 'POST'])
    def search_packages():
        query = request.args.get('query', '').strip().lower()  
        min_price = request.args.get('min_price', type=float)  
        max_price = request.args.get('max_price', type=float)  
        user=current_user
        app.logger.info(f"Search initiated: query='{query}', min_price={min_price}, max_price={max_price}")

        
        packages = []

        if not query:
            app.logger.info("Empty query string provided; skipping database search.")
            return render_template(
                'search_results.html',
                packages=[],
                query=query,
                message="Please provide a search query to find packages."
            )

        try:
            
            services_query = Service.query.filter(
                (Service.servicename.ilike(f"%{query}%")) |
                (Service.description.ilike(f"%{query}%"))
            )

            if min_price is not None:
                services_query = services_query.filter(Service.price >= min_price)
            if max_price is not None:
                services_query = services_query.filter(Service.price <= max_price)

            services = services_query.all()
            app.logger.info(f"Services found: {[service.servicename for service in services]}")

            
            if services:
                service_ids = [service.id for service in services]
                packages = Package.query.filter(Package.service_id.in_(service_ids)).all()
                app.logger.info(f"Packages found: {[pkg.name for pkg in packages]}")

        except Exception as e:
            app.logger.error(f"Error during search: {e}")
            return render_template('error.html', error_message="An error occurred during the search.")

        if not packages:
            app.logger.info("No packages found for the query.")
            return render_template(
                'search_results.html',
                packages=[],
                query=query,
                message="No packages found for the given query."
            )

        return render_template('search_results.html', packages=packages, query=query, user=user)

    @app.route('/prodash', methods=['GET'])
    @login_required
    def prodash():
        
        pro = ServiceProfessional.query.get(current_user.id)
        if not pro:
            return render_template("loginpro.html", msg="Professional not found"), 404

        requests = (
            ServiceRequest.query
            .join(Service, ServiceRequest.service_id == Service.id)
            .filter(
                Service.servicename == pro.servicename,
                or_(
                    ServiceRequest.status == StatusEnum.Pending.value,
                    ServiceRequest.status == StatusEnum.In_progress.value,
                    ServiceRequest.status == StatusEnum.Completed.value,
                    ServiceRequest.status == StatusEnum.Rejected.value,
                    ServiceRequest.status == StatusEnum.Cancelled.value,
                    ServiceRequest.status == StatusEnum.Accepted.value
                    

                )
            )
            .all()
        )

        
        for request in requests:
            package = Package.query.get(request.package_id)
            request.pkg_name = package.name if package else "No Package"
            request.price= package.price if package else 0

        return render_template('professional_dashboard.html',pro=pro,requests=requests)


    @app.route("/progress_request/<int:request_id>", methods=["POST"])
    @login_required
    def progress_request(request_id):
        
        request = ServiceRequest.query.get_or_404(request_id)
        request.status = StatusEnum.In_progress.value  
        db.session.commit()
        return redirect(url_for("prodash"))

    @app.route("/reject_request/<int:request_id>", methods=["POST"])
    @login_required
    def reject_request(request_id):
        
        request = ServiceRequest.query.get_or_404(request_id)
        request.status = StatusEnum.Rejected.value  
        db.session.commit()
        flash("Request is now Rejected.")
        return redirect(url_for("prodash"))
    
    @app.route("/completed_request/<int:request_id>", methods=["POST"])
    @login_required
    def completed_request(request_id):
        
        request = ServiceRequest.query.get_or_404(request_id)
        request.status = StatusEnum.Completed.value  
        db.session.commit()
        flash("Request Completed successfully.")
        return redirect(url_for("cushome"))
    @app.route("/cancel_request/<int:request_id>", methods=["POST"])
    def cancel_request(request_id):
        try:
            request_to_update =ServiceRequest.query.get_or_404(request_id)
            if request_to_update:
                request_to_update.status = 'Cancelled'
                db.session.commit()
                flash("Request has been successfully cancelled.", "success")
            else:
                flash("Request not found.", "danger")
        except Exception as e:
            print("Error updating request:", e)
            flash("An error occurred while updating the request.", "danger")
        
        return redirect(url_for("cushome"))
    @app.route('/rate/<int:service_request_id>', methods=['GET', 'POST'])
    def rate_service(service_request_id):
        service_request = ServiceRequest.query.get_or_404(service_request_id)
        service_professional_id = service_request.professional_id
        if not service_professional_id:
            return "Service Professional ID is missing!", 400
        
        if request.method == 'POST':
            rating_value = request.form['rating']
            comment = request.form.get('comment', '')  
            
            
            rating = Rating(
                customer_id=service_request.customer_id,
                professional_id=service_request.professional_id,
                service_request_id=service_request.id,
                rating=int(rating_value),
                comment=comment
            )
            db.session.add(rating)
            db.session.commit()
            
            flash("Thank you for your feedback!", "success")
            return redirect(url_for('cushome'))
        
        return render_template('rate_service.html', service_professional_id=service_professional_id, service_request_id=service_request_id)
    @app.route("/accept_request/<int:request_id>", methods=["POST"])
    @login_required
    def accept_request(request_id):
        try:
            service_request = ServiceRequest.query.get(request_id)
            if not service_request:
                return "Request not found", 404
            
            # Update the professional_id and status
            service_request.professional_id = current_user.id
            service_request.status = StatusEnum.Accepted.value
            db.session.commit()

            return redirect(url_for('prodash'))
        except SQLAlchemyError as e:
            db.session.rollback()
            return f"Database error: {str(e)}", 500 
    @app.route("/delete_servicepro/<int:pro_id>", methods=["POST"])
    @login_required
    def delete_servicepro(pro_id):
        
        service_professional = ServiceProfessional.query.get_or_404(pro_id)

        try:
            
            db.session.delete(service_professional)
            db.session.commit()
            flash('Professional deleted successfully!', 'success')
        except SQLAlchemyError as e:
            
            db.session.rollback()
            flash(f'Error deleting service professional: {str(e)}', 'error')

        return redirect(url_for('adminhome'))
    
    @app.route('/adminedit/<int:request_id>',methods=['GET','POST'])
    @login_required
    def adminedit(request_id):
        requests = ServiceRequest.query.all()
        professionals = ServiceProfessional.query.all()
        return render_template("adminedit.html",request_id=request_id,requests=requests,professionals=professionals)
    
    @app.route('/admin/change_professional/<int:request_id>', methods=['POST'])
    def change_professional(request_id):
        service_request = ServiceRequest.query.get_or_404(request_id)
        new_professional_id = request.form.get('professional_id')
        service_request.professional_id = new_professional_id
        db.session.commit()
        flash('Service professional updated successfully', 'success')
        return redirect(url_for('adminhome'))
    
    @app.route('/admin/cancel_requestadmin/<int:request_id>', methods=['POST'])
    def cancel_requestadmin(request_id):
        service_request = ServiceRequest.query.get_or_404(request_id)
        service_request.status = StatusEnum.Cancelled
        service_request.date_of_completion = datetime.utcnow()
        db.session.commit()
        flash('Service request canceled successfully', 'success')
        return redirect(url_for('adminhome'))
    
    @app.route("/admincompleted_request/<int:request_id>", methods=["POST"])
    @login_required
    def admincompleted_request(request_id):
        
        request = ServiceRequest.query.get_or_404(request_id)
        request.status = StatusEnum.Completed.value 
        db.session.commit()
        flash("Request Completed successfully.")
        return redirect(url_for("adminhome"))
    
    @app.route("/block_professional/<int:professional_id>", methods=["POST","GET"])
    @login_required
    def block_professional(professional_id):
        professional = ServiceProfessional.query.get_or_404(professional_id)
        professional.block = 1 
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()  
            print(f"Error blocking professional: {e}")
            return "Error occurred while blocking."
        return redirect(url_for("adminhome"))

    @app.route("/unblock_professional/<int:professional_id>", methods=["POST","GET"])
    @login_required
    def unblock_professional(professional_id):
        professional = ServiceProfessional.query.get_or_404(professional_id)
        professional.block = 0 #Flase
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error unblocking professional: {e}")
            return "Error occurred while unblocking."
        return redirect(url_for("adminhome"))
    
    @app.route("/block_customer/<int:customer_id>", methods=["POST","GET"])
    @login_required
    def block_customer(customer_id):
        customer = Customer.query.get_or_404(customer_id)
        customer.block = 1 #true
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()  
            print(f"Error blocking customer: {e}")
            return "Error occurred while blocking."
        return redirect(url_for("adminhome"))

    @app.route("/unblock_customer/<int:customer_id>", methods=["POST","GET"])
    @login_required
    def unblock_customer(customer_id):
        customer = Customer.query.get_or_404(customer_id)
        customer.block = 0 
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error unblocking professional: {e}")
            return "Error occurred while unblocking."
        return redirect(url_for("adminhome"))
    @app.route("/Approve_professional/<int:professional_id>", methods=["POST","GET"])
    @login_required
    def Approve_professional(professional_id):
        professional = ServiceProfessional.query.get_or_404(professional_id)
        professional.Approve = 1 
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()  
            print(f"Error blocking professional: {e}")
            return "Error occurred while blocking."
        return redirect(url_for("adminhome"))

    @app.route("/Reject_professional/<int:professional_id>", methods=["POST","GET"])
    @login_required
    def Reject_professional(professional_id):
        professional = ServiceProfessional.query.get_or_404(professional_id)
        professional.Approve = 0 
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error unblocking professional: {e}")
            return "Error occurred while unblocking."
        return redirect(url_for("adminhome"))
    @app.route("/Update_package/<int:package_id>", methods=["POST","GET"])
    @login_required
    def Update_package(package_id):
        package = Package.query.get_or_404(package_id)
        if request.method == "POST":
            package.name = request.form.get("name")
            package.price = request.form.get("price")
            package.description = request.form.get("description")
            db.session.commit()
            return redirect(url_for("adminhome"))   
    @app.route("/Delete_package/<int:package_id>", methods=["POST","GET"])
    @login_required
    def Delete_package(package_id): 
        package = Package.query.get_or_404(package_id)
        if request.method == "POST":
            db.session.delete(package)
            db.session.commit()
            return redirect(url_for("adminhome"))   
        
# Create the app object globally so Gunicorn can find it
app = create_app()
register_routes(app)

if __name__ == "__main__":
    # This only runs for local development
    app.run(debug=True)


