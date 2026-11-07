import os
import pandas as pd
import csv
import hashlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io
import base64
import random
import time
import smtplib
import secrets
from functools import wraps
import ssl
from email.message import EmailMessage
from datetime import datetime 
from sklearn.metrics import accuracy_score
from collections import Counter, defaultdict
import shutil
from flask import Flask, render_template, request, redirect, url_for, session

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash,check_password_hash
from datetime import datetime
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score



# Define the project folder first
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define the CSV file location
DATA_FOLDER = os.path.join(BASE_DIR, "data")
OWNER_FILE = os.path.join(DATA_FOLDER, "owners.csv")
ACCURACY_FILE=os.path.join(DATA_FOLDER,"owner_accuracy.csv")
ADMINN_FILE=os.path.join(DATA_FOLDER,"admin.csv")
FEEDBACK_FILE=os.path.join(DATA_FOLDER,"feedback.csv")
LOGIN_HISTORY_FILE = os.path.join(
DATA_FOLDER, "owners_login_history.csv"
)

os.makedirs(DATA_FOLDER, exist_ok=True)

#GMAIL CONFIGURATION

MAIL_ADDRESS = os.getenv("MAIL_ADDRESS")
MAIL_APP_PASSWORD = os.getenv("MAIL_APP_PASSWORD")
os.getenv("MAIL_APP_PASSWORD")

#OTP EMAIL FUNCTION
def send_admin_otp(receiver_email, otp):

    message = EmailMessage()

    message["Subject"] = "Smart Buy - Admin Password Reset OTP"
    message["From"] = MAIL_ADDRESS
    message["To"] = receiver_email

    message.set_content(f"""
Hello Admin,

Your Smart Buy password reset OTP is:

{otp}

This OTP is valid for 5 minutes.

Do not share this OTP with anyone.

Thank you,
Smart Buy Team
""")

    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            context=ssl.create_default_context()
        ) as server:

            server.login(MAIL_ADDRESS, MAIL_APP_PASSWORD)
            server.send_message(message)

        return True

    except Exception as error:
        print("OTP email error:", error)
        return False
    


# Create the Flask app after BASE_DIR is defined

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "pages"),
    static_folder=os.path.join(BASE_DIR, "frontend"),
    static_url_path="/static"
)


app.secret_key = "smart_buy_secret_demo_key"


def get_owner_csv_path(owner_email=None):

    if owner_email is None:
        owner_email = session.get("owner_email", "")

    owner_email = owner_email.strip().lower()

    if not owner_email:
        raise ValueError("Owner email not found.")

    owner_folder = hashlib.sha256(
        owner_email.encode("utf-8")
    ).hexdigest()

    base_dir = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(
        base_dir,
        "data",
        "customers",
        owner_folder,
        "customer-data.csv"
    )


UPLOAD_FOLDER = os.path.join(BASE_DIR, "UPLOAD_FOLDER")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#OWNER CAN ADD CSV FILE THAT STORES
OWNER_FILE = "owners.csv"
ADMIN_FILE= "admin.csv"
LOGIN_HISTORY_FILE="owner_login_history.csv"
FEEDBACK_FILE = "feedback.csv"


#Home page
@app.route("/")
def home():
    return render_template("home.html")


#register page flask
@app.route("/owner-register", methods=["GET", "POST"])
def owner_register():

    if request.method == "GET":
        return render_template("owner_register.html")

    owner_name = request.form.get("owner_name", "").strip()
    company = request.form.get("company", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not owner_name or not company or not email or not password:
        return render_template(
            "owner_register.html",
            error="Please fill in all fields."
        )

    os.makedirs(DATA_FOLDER, exist_ok=True)

    owners = []

    if os.path.exists(OWNER_FILE):
        with open(OWNER_FILE, "r", newline="", encoding="utf-8") as file:
            owners = list(csv.DictReader(file))

    for owner in owners:
        if owner.get("email", "").strip().lower() == email:
            return render_template(
                "owner_register.html",
                error="This email is already registered."
            )

    # Get registration date and time
    registration_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    fieldnames = [
        "owner_name",
        "company",
        "email",
        "password_hash",
        "registration_time"
    ]

    file_exists = os.path.exists(OWNER_FILE) and os.path.getsize(OWNER_FILE) > 0

    with open(OWNER_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "owner_name": owner_name,
            "company": company,
            "email": email,
            "password_hash": generate_password_hash(password),
            "registration_time": registration_time
        })

        

    session["owner_name"] = owner_name
    session["owner_email"] = email
    session["company"] = company

    return render_template(
        "owner_register.html",
        registration_success=True
    )

      


#owner_login page flask
# Owner Login
@app.route("/owner-login", methods=["GET", "POST"])
def owner_login():

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not os.path.exists(OWNER_FILE):
            return "No registered owners found. Please register first."

        with open(OWNER_FILE, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for owner in reader:
                saved_email = owner.get("email", "").strip().lower()

                # Support hashed passwords and older plain-text records
                saved_hash = owner.get("password_hash", "").strip()
                saved_password = owner.get("password", "")

                password_matches = False

                if saved_hash:
                    password_matches = check_password_hash(
                        saved_hash, password
                    )
                elif saved_password:
                    password_matches = saved_password == password

                if saved_email == email and password_matches:

                    session["owner_name"] = owner.get("owner_name", "")
                    session["owner_email"] = email

                    # Record owner login date and time
                    file_exists = (
                        os.path.exists(LOGIN_HISTORY_FILE)
                        and os.path.getsize(LOGIN_HISTORY_FILE) > 0
                    )

                    with open(
                        LOGIN_HISTORY_FILE,
                        "a",
                        newline="",
                        encoding="utf-8"
                    ) as history_file:

                        fieldnames = [
                            "owner_name",
                            "company",
                            "email",
                            "login_at"
                        ]

                        writer = csv.DictWriter(
                            history_file,
                            fieldnames=fieldnames
                        )

                        if not file_exists:
                            writer.writeheader()

                        writer.writerow({
                            "owner_name": owner.get("owner_name", ""),
                            "company": owner.get("company", ""),
                            "email": email,
                            "login_at": datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        })

                    # Redirect only after successful login
                    return redirect("/owner-dashboard")

        return "Invalid email or password. Please try again.", 401

    return render_template("owner_login.html")



# Owner Logout
@app.route("/owner-logout")
def owner_logout():
    session.clear()
    return redirect("/") 

# Show logout confirmation page

@app.route("/logout")
def logout_page():
    if "owner_name" not in session:
        return redirect("/owner-login")
    return render_template("logout.html")


@app.route("/save-logout")
def save_logout():
    session.clear()
    return redirect("/")


#UPLOAD DATASET ROUTE
@app.route("/upload-dataset", methods=["POST"])
def upload_dataset():

    if "owner_name" not in session:
        return redirect("/owner-login")

    uploaded_file = request.files.get("customer_file")

    if not uploaded_file or not uploaded_file.filename:
        return redirect("/owner-dashboard")

    if not uploaded_file.filename.lower().endswith(".csv"):
        return render_template(
            "owner-dashboard.html",
            error="Please upload a CSV file.",
            total_customers=0,
            uploaded_filename=None,
            purchase_count=0,
            no_purchase_count=0,
            columns=[],
            customer_data=[],
            purchase_labels=[],
            purchase_values=[],
            gender_labels=[],
            gender_values=[],
            category_labels=[],
            category_values=[]
        )

    try:
    
        # Get the original uploaded filename
        original_filename = secure_filename(uploaded_file.filename)

        # Read the uploaded CSV file
        df = pd.read_csv(uploaded_file)

        if df.empty:
            raise ValueError("The uploaded CSV contains no records.")

        # Get the owner's CSV path
        csv_path = get_owner_csv_path()

        # Create the owner's folder if it does not exist
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)

        # Save the original filename for display
        filename_path = os.path.join(
            os.path.dirname(csv_path),
            "uploaded_filename.txt"
        )

        with open(filename_path, "w", encoding="utf-8") as file:
            file.write(original_filename)

        # Save customer data
        df.to_csv(csv_path, index=False)

        # Return to dashboard after upload
        return redirect("/owner-dashboard?uploaded=1")

    except Exception as e:
        return render_template(
            "owner-dashboard.html",
            error=f"Could not upload CSV: {e}",
            total_customers=0,
            uploaded_filename=None,
            purchase_count=0,
            no_purchase_count=0,
            columns=[],
            customer_data=[],
            purchase_labels=[],
            purchase_values=[],
            gender_labels=[],
            gender_values=[],
            category_labels=[],
            category_values=[]
        )

@app.route("/remove-dataset", methods=["GET", "POST"])
def remove_dataset():

    if "owner_name" not in session:
        return redirect("/owner-login")

    csv_path = get_owner_csv_path()

    # Remove only this owner's customer CSV
    if os.path.exists(csv_path):
        os.remove(csv_path)

    # Remove the saved original filename, if it exists
    filename_path = os.path.join(
        os.path.dirname(csv_path),
        "uploaded_filename.txt"
    )

    if os.path.exists(filename_path):
        os.remove(filename_path)

    return redirect("/owner-dashboard? uploaded=1") 

#PURCHASE-PREDICTION
@app.route("/prediction", methods=["GET", "POST"])
def prediction():

    categories = [
    "Kitchen",
    "Electronics",
    "Sports",
    "Clothes",
    "Stationery",
    "Accessories",
    "Furniture",
    "Beauty Products",
    "Footwear",
    "Jewellery",
    "Home Decor",
    "Books",
    "Groceries"
]

    # Check owner login
    if "owner_email" not in session:
        return redirect("/owner-login")

    # Show the prediction form
    if request.method == "GET":
        return render_template("purchase_prediction.html")

    try:
        # Get this owner's uploaded CSV file
        csv_path = get_owner_csv_path()

        if not os.path.exists(csv_path):
            return render_template(
                "purchase_prediction.html",
                error="Please upload your customer CSV file first."
            )

        # Train the model using this owner's dataset
        model, feature_columns, model_accuracy = train_purchase_model(csv_path)
        save_owner_accuracy(model_accuracy)
        save_owner_accuracy(feature_columns)

        # Read form values
        age = int(request.form.get("age", "").strip())
        gender = request.form.get("gender", "").strip()
        category = request.form.get("purchase_category", "").strip()
        previous_purchase = int(request.form["previous_purchase"])
        website_time = int(request.form["website_visited_time"])
        

        # Use the same feature names as the training dataset
        

        # Include only features used by the trained model
        customer = pd.DataFrame([{
            "age": age,
            "gender": gender,
            "category": category,
            "previous_purchase": previous_purchase,
            "website_visited_time": website_time
        }])

        # Predict Purchase or No Purchase
        prediction = model.predict(customer)[0]

        # Get probability for the predicted class
        probabilities = model.predict_proba(customer)[0]
        classes = list(model.classes_)

        predicted_index = classes.index(prediction)
        prediction_percentage = float(probabilities[predicted_index] * 100)

        return render_template(
            "purchase_prediction.html",
            prediction=prediction,
            prediction_percentage=prediction_percentage,
            customer_age=age,
            customer_gender=gender,
            categories=categories,
            purchase_category=category,
            error=None
        )

    except (ValueError, TypeError) as e:
        return render_template(
            "purchase_prediction.html",
            error=f"Please check your input: {e}"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()

        return render_template(
            "purchase_prediction.html",
            error=f"Prediction error: {type(e).__name__}: {e}",
            categories=categories
        )
    
#model_accuracy ggraph
def save_owner_accuracy(model_accuracy):
    import csv

    if model_accuracy is None:
        return

    try:
        accuracy = float(model_accuracy)

        if 0 <= accuracy <= 1:
            accuracy *= 100

        if not 0 <= accuracy <= 100:
            return

        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)

        ACCURACY_FILE = os.path.join(data_dir, "owner_accuracy.csv")

        owner_name = session.get("owner_name", "Unknown")
        company = session.get("company", "Unknown")

        rows = []

        if os.path.exists(ACCURACY_FILE):
            with open(ACCURACY_FILE, "r", newline="", encoding="utf-8-sig") as file:
                rows = list(csv.DictReader(file))

        # Update this owner's existing record, if available
        owner_found = False

        for row in rows:
            if row.get("owner_name") == owner_name:
                row["company"] = company
                row["model_accuracy"] = f"{accuracy:.2f}"
                owner_found = True
                break

        if not owner_found:
            rows.append({
                "owner_name": owner_name,
                "company": company,
                "model_accuracy": f"{accuracy:.2f}"
            })

        with open(ACCURACY_FILE, "w", newline="", encoding="utf-8") as file:
            fieldnames = [
                "owner_name",
                "company",
                "model_accuracy"
            ]

            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()

            for row in rows:
                writer.writerow({
                    "owner_name": row.get("owner_name", ""),
                    "company": row.get("company", ""),
                    "model_accuracy": row.get("model_accuracy", "")
                })

    except (ValueError, TypeError, OSError) as e:
        print("Could not save owner accuracy:", e)


#OWNER DASHBOARD ROUTE
# OWNER DASHBOARD ROUTE
@app.route("/owner-dashboard")
def owner_dashboard():

    if "owner_name" not in session:
        return redirect("/owner-login")

    try:
        csv_path = get_owner_csv_path()

        # Default values
        df = pd.DataFrame()
        uploaded_filename = None

        # Read the owner's uploaded CSV
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)

            filename_path = os.path.join(
                os.path.dirname(csv_path),
                "uploaded_filename.txt"
            )

            if os.path.exists(filename_path):
                with open(filename_path, "r", encoding="utf-8") as file:
                    uploaded_filename = file.read().strip()
            else:
                uploaded_filename = os.path.basename(csv_path)

        # Normalize column names
        if not df.empty:
            df.columns = [
                str(c).strip().lower().replace(" ", "_")
                for c in df.columns
            ]

            for column in [
                "age",
                "previous_purchase",
                "website_visited_time"
            ]:
                
                if column in df.columns:
                    df[column] = pd.to_numeric(
                        df[column],
                        errors="coerce"
                    )

        total_customers = len(df)
        has_dataset=not df.empty

        # -------------------------
        # MODEL ACCURACY
        # -------------------------
        model_accuracy = None
        accuracy_message = None

        if os.path.exists(csv_path) and not df.empty:
            try:
                trained_model, feature_columns, model_accuracy = (
                    train_purchase_model(csv_path)
                )

                if model_accuracy is not None:
                    save_owner_accuracy(model_accuracy)
                else:
                    accuracy_message = "Model accuracy is not available."

            except (ValueError, TypeError) as e:
                accuracy_message = str(e)

        # -------------------------
        # PURCHASE / NOT PURCHASE
        # -------------------------
        purchase_count = 0
        no_purchase_count = 0

        purchase_column = next(
            (
                c for c in [
                    "purchase_status",
                    "purchase",
                    "purchased",
                    "purchase_or_not_purchase"
                ]
                if c in df.columns
            ),
            None
        )

        if purchase_column:
            status = (
                df[purchase_column]
                .astype(str)
                .str.strip()
                .str.lower()
            )

            yes_values = ["yes", "1", "true", "purchase", "purchased"]
            no_values = ["no", "0", "false", "not purchase",
                         "not purchased", "no purchase"]

            purchase_count = int(status.isin(yes_values).sum())
            no_purchase_count = int(status.isin(no_values).sum())

        purchase_labels = ["Purchase", "Not Purchase"]
        purchase_values = [purchase_count, no_purchase_count]

        # -------------------------
        # GENDER DISTRIBUTION
        # -------------------------
        # Gender Distribution
        gender_column = next(
            (
                c for c in df.columns
                if c.replace("_", "").replace(" ", "").lower()
                in ["gender", "customergender"]
            ),
            None
        )

        if gender_column:
            gender = (
                df[gender_column]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
            )

            gender = gender.replace({
                "m": "Male",
                "male": "Male",
                "f": "Female",
                "female": "Female"
            })

            # Normalize gender values
            gender = gender.astype(str).str.strip().str.lower()

            gender = gender.replace({
                "m": "Male",
                "male": "Male",
                "0": "Male",
                "f": "Female",
                "female": "Female",
                "1": "Female"
            })

            gender = gender[gender.isin(["Male", "Female"])]

            gender_counts = gender.value_counts()

            gender_labels = ["Male", "Female"]
            gender_values = [
                int(gender_counts.get("Male", 0)),
                int(gender_counts.get("Female", 0))
            ]   
            
        else:
            gender_labels = []
            gender_values = []
        
        # -------------------------
        # CATEGORY SUMMARY
        # -------------------------
        category_column = next(
            (
                c for c in [
                    "category",
                    "purchase_category",
                    "product_category",
                    "previous_purchase"
                ]
                if c in df.columns
            ),
            None
        )

        if category_column:
            category_counts = (
                df[category_column]
                .dropna()
                .astype(str)
                .str.strip()
            )

            category_counts = category_counts[
                category_counts != ""
            ].value_counts()

            category_labels = category_counts.index.tolist()
            category_values = [
                int(value) for value in category_counts.values
            ]
        else:
            category_labels = []
            category_values = []

        # -------------------------
        # CUSTOMER TABLE
        # -------------------------
        columns = df.columns.tolist()

        customer_data = (
            df.fillna("").to_dict(orient="records")
            if not df.empty else []
        )

        return render_template(
            "owner-dashboard.html",
            total_customers=total_customers,
            uploaded_filename=uploaded_filename,
            purchase_count=purchase_count,
            no_purchase_count=no_purchase_count,
            columns=columns,
            customer_data=customer_data,
            purchase_labels=purchase_labels,
            purchase_values=purchase_values,
            gender_labels=gender_labels,
            gender_values=gender_values,
            category_labels=category_labels,
            category_values=category_values,
            model_accuracy=model_accuracy,
            accuracy_message=accuracy_message,
            has_dataset=has_dataset
        )

    except Exception as e:
                return f"Dashboard error: {e}", 500
        

  
 

# OWNER-FEEDBACK
@app.route("/owner-feedback", methods=["GET", "POST"])
def owner_feedback():

    # Only logged-in owners can access feedback
    if "owner_name" not in session:
        return redirect(url_for("owner_login"))

    # Create CSV with headers if it does not exist
    if not os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                "owner_name", "company", "rating",
                "feedback", "date"
            ])

    success = None
    error = None

    if request.method == "POST":
        rating = request.form.get("rating", "").strip()
        feedback = request.form.get("feedback", "").strip()

        if rating not in ["1", "2", "3", "4", "5"]:
            error = "Please select a valid rating."

        elif not feedback or len(feedback) > 1000:
            error = "Feedback must contain 1 to 1000 characters."

        else:
            owner_name = session.get("owner_name", "")
            company = session.get("company", "")

            # Get company from your existing owner CSV
            if not company:
                owner_file = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "owner.csv"
                )

                if os.path.exists(owner_file):
                    with open(
                        owner_file, "r", newline="", encoding="utf-8"
                    ) as file:
                    
                        for owner in csv.DictReader(file):
                            if (
                                owner.get("owner_name", "").strip()
                                == owner_name
                            ):
                                company = (
                                    owner.get("company", "")
                                    or owner.get("company_name", "")
                                )
                                break

            # Append feedback; never overwrite existing feedback
            with open(
                FEEDBACK_FILE, "a", newline="", encoding="utf-8"
            ) as file:
                writer = csv.writer(file)
                writer.writerow([
                    owner_name,
                    company,
                    rating,
                    feedback,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ])

            return redirect(url_for("owner_feedback", submitted="1"))

    if request.args.get("submitted") == "1":
        success = "Your feedback was submitted successfully!"

    # Read all owners' feedback
    with open(
        FEEDBACK_FILE, "r", newline="", encoding="utf-8"
    ) as file:
        feedbacks = list(csv.DictReader(file))

    feedbacks.reverse()
     
     # owner-feedback.html from your frontnend/pages/ folder
    return render_template(
        "owner-feedback.html",
        feedbacks=feedbacks,
        success=success,
        error=error
    )



#TAIN_MODEL
# TRAIN DECISION TREE FOR PURCHASE / NO PURCHASE
def train_purchase_model(csv_path):
    # Check whether the owner's CSV file exists
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            "Customer dataset not found. Please upload a CSV file first."
        )

    # Read the uploaded CSV file
    df = pd.read_csv(csv_path)

    # Clean column names
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
    )

    # Required columns
    required_columns = [
        "age",
        "gender",
        "category",
        "purchase_status"
    ]

    # Check required columns
    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required CSV columns: "
            + ", ".join(missing_columns)
        )

    # Keep only required columns
    df = df[required_columns].copy()

    # Clean input data
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["gender"] = df["gender"].astype("string").str.strip()
    df["category"] = df["category"].astype("string").str.strip()

    # Clean target values
    df["purchase_status"] = (
        df["purchase_status"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    # Standardize purchase labels
    df["purchase_status"] = df["purchase_status"].map({
        "yes": "Yes",
        "no": "No",
        "purchase": "Yes",
        "not purchase": "No",
        "not_purchase": "No"
    })

    # Remove rows with missing values
    df = df.dropna(subset=required_columns)

    # Remove empty text values
    df = df[
        (df["gender"] != "")
        & (df["category"] != "")
    ]

    # Check usable data
    if len(df) < 4:
        raise ValueError(
            "Please upload a CSV containing at least 4 valid customer records."
        )

    # Separate features and target
    X = df[["age", "gender", "category"]]
    y = df["purchase_status"]

    if y.nunique() < 2:
        raise ValueError(
            "Purchase_Status must contain both Yes and No examples."
        )

    # Numeric preprocessing
    numeric_pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median"))
    ])

    # Categorical preprocessing
    categorical_pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore"))
    ])

    # Combine preprocessing
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, ["age"]),
            ("categorical", categorical_pipeline, ["gender", "category"])
        ]
    )

    # Create Decision Tree model
    model = Pipeline(steps=[
        ("preprocessor", preprocessor),
        (
            "classifier",
            DecisionTreeClassifier(
                max_depth=5,
                min_samples_leaf=3,
                random_state=42
            )
        )
    ])

    # Train using this owner's uploaded CSV
    model.fit(X, y)

    # Calculate training accuracy on the same uploaded data
    y_pred = model.predict(X)

    model_accuracy = round(
        accuracy_score(y, y_pred) * 100,
        2
    )

    # Return model, input columns, and accuracy
    feature_columns = [
        "age",
        "gender",
        "category"
    ]

    return model, feature_columns, model_accuracy

#ADNMIN FEEDBACK
@app.route("/admin-feedback")
def admin_feedback():

    # Only logged-in admins can access this page
    if "admin_email" not in session:
        return redirect("/admin-login")

    feedback_list = []

    # Read all owner feedback
    if os.path.exists(FEEDBACK_FILE):
        with open(
            FEEDBACK_FILE, "r", newline="", encoding="utf-8"
        ) as file:
            feedback_list = list(csv.DictReader(file))

    # Show newest feedback first
    feedback_list.reverse()

    return render_template(
        "admin-feedback.html",
        feedback_list=feedback_list,
        admin_name=session.get("admin_name", "Admin")
    )
#FEEDBACK EDIT
@app.route("/admin-feedback/edit/<int:feedback_id>", methods=["GET", "POST"])
def admin_edit_feedback(feedback_id):

    if "admin_email" not in session:
        return redirect("/admin-login")

    feedbacks = []

    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r", newline="", encoding="utf-8") as file:
            feedbacks = list(csv.DictReader(file))

    feedbacks.reverse()

    if feedback_id < 0 or feedback_id >= len(feedbacks):
        return "Feedback not found.", 404

    feedback = feedbacks[feedback_id]

    if request.method == "POST":
        new_rating = request.form.get("rating", "").strip()
        new_feedback = request.form.get("feedback", "").strip()

        if new_rating not in ["1", "2", "3", "4", "5"]:
            return "Please select a valid rating.", 400

        if not new_feedback or len(new_feedback) > 1000:
            return "Feedback must contain 1 to 1000 characters.", 400

        feedback["rating"] = new_rating
        feedback["feedback"] = new_feedback

        # Restore original CSV order
        feedbacks.reverse()

        with open(FEEDBACK_FILE, "w", newline="", encoding="utf-8") as file:
            fieldnames = ["owner_name", "company", "rating", "feedback", "date"]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(feedbacks)

        return redirect("/admin-feedback")

    return render_template(
        "admin-edit-feedback.html",
        feedback=feedback,
        feedback_id=feedback_id
    )

#FEEDBACK DELETE
@app.route("/admin-feedback/delete/<int:feedback_id>", methods=["POST"])
def admin_delete_feedback(feedback_id):

    if "admin_email" not in session:
        return redirect("/admin-login")

    if not os.path.exists(FEEDBACK_FILE):
        return redirect("/admin-feedback")

    with open(FEEDBACK_FILE, "r", newline="", encoding="utf-8") as file:
        feedbacks = list(csv.DictReader(file))

    # Match the newest-first order shown on the admin page
    feedbacks.reverse()

    if feedback_id < 0 or feedback_id >= len(feedbacks):
        return "Feedback not found.", 404

    feedbacks.pop(feedback_id)

    # Restore original CSV order
    feedbacks.reverse()

    with open(FEEDBACK_FILE, "w", newline="", encoding="utf-8") as file:
        fieldnames = ["owner_name", "company", "rating", "feedback", "date"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(feedbacks)

    return redirect("/admin-feedback")
  

#ADMIN-REGISTER PAGE
@app.route("/admin-register", methods=["GET", "POST"])
def admin_register():

    # Check whether an admin is already registered
    if os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE, "r", newline="", encoding="utf-8-sig") as file:
            admins = list(csv.DictReader(file))
    else:
        admins = []

    # If an admin already exists, block registration
    if admins:
        return redirect(url_for("admin_login"))

    # Process registration form
    if request.method == "POST":

        admin_name = request.form.get("admin_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Validate input
        if not admin_name or not email or len(password) < 8:
            return render_template(
                "admin-register.html",
                error="Enter all details. Password must have at least 8 characters."
            )

        # Check again before saving
        if os.path.exists(ADMIN_FILE):
            with open(ADMIN_FILE, "r", newline="", encoding="utf-8-sig") as file:
                admins = list(csv.DictReader(file))
        else:
            admins = []

        if admins:
            return redirect(url_for("admin_login"))

        # Save admin details with a hashed password
        with open(ADMIN_FILE, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["admin_name", "email", "password"]
            )

            writer.writeheader()

            writer.writerow({
                "admin_name": admin_name,
                "email": email,
                "password": generate_password_hash(password)
            })

        # Log in the newly registered admin
        session["admin_email"] = email
        session["admin_name"] = admin_name

        # Redirect directly to Admin Dashboard
        return """
        <script>
            alert("Admin registration successful!");
            window.location.href = "/admin-dashboard";
        </script>
        """

    # Display registration page
    return render_template("admin-register.html")

#ADMIN-LOGIN PATH
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Check whether the admin CSV file exists
        if not os.path.exists(ADMIN_FILE):
            return render_template(
                "admin-login.html",
                error="No admin registered yet. Please register first."
            )

        # Read the registered admin details
        with open(ADMIN_FILE, "r", newline="", encoding="utf-8-sig") as file:
            admins = list(csv.DictReader(file))

        # Verify email and password
        for admin in admins:
            if (
                admin["email"].strip().lower() == email
                and check_password_hash(admin["password"], password)
            ):
                session["admin_email"] = admin["email"]
                session["admin_name"] = admin["admin_name"]

                return redirect("/admin-dashboard")

        return render_template(
            "admin-login.html",
            error="Invalid email or password."
        )

    return render_template("admin-login.html")



# Temporary OTP storage
ADMIN_OTP_STORE = {}
@app.route("/admin-forgot-password", methods=["GET", "POST"])
def admin_forgot_password():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        # Check registered admin email
        admins = []

        if os.path.exists(ADMIN_FILE):
            with open(ADMIN_FILE, "r", newline="", encoding="utf-8-sig") as file:
                admins = list(csv.DictReader(file))

        admin_found = any(
            row.get("email", "").strip().lower() == email
            for row in admins
        )

        if not admin_found:
            return render_template(
                "admin-forgot-password.html",
                message="If the account exists, an OTP will be sent."
            )

        # Generate 6-digit OTP
        otp = f"{secrets.randbelow(1000000):06d}"

        # Store hashed OTP with 5-minute expiry
        ADMIN_OTP_STORE[email] = {
            "otp_hash": hashlib.sha256(otp.encode()).hexdigest(),
            "expires_at": time.time() + 300,
            "attempts": 0
        }

        # Send OTP email
        if send_admin_otp(email, otp):

            session["admin_reset_email"] = email

            return redirect(url_for("admin_verify_otp"))

        ADMIN_OTP_STORE.pop(email, None)

        return render_template(
            "admin-forgot-password.html",
            message="Unable to send OTP. Please try again."
        )

    return render_template("admin-forgot-password.html")

#admin-verify route
@app.route("/admin-verify-otp", methods=["GET", "POST"])
def admin_verify_otp():

    email = session.get("admin_reset_email")

    if not email or email not in ADMIN_OTP_STORE:
        return redirect(url_for("admin_forgot_password"))

    otp_data = ADMIN_OTP_STORE[email]

    if time.time() > otp_data["expires_at"]:
        ADMIN_OTP_STORE.pop(email, None)
        session.pop("admin_reset_email", None)

        return render_template(
            "admin-verify-otp.html",
            message="OTP expired. Please request a new OTP."
        )

    if request.method == "POST":

        entered_otp = request.form.get("otp", "").strip()

        if not entered_otp.isdigit() or len(entered_otp) != 6:
            return render_template(
                "admin-verify-otp.html",
                message="Enter a valid 6-digit OTP."
            )

        entered_hash = hashlib.sha256(
            entered_otp.encode()
        ).hexdigest()

        if secrets.compare_digest(
            entered_hash,
            otp_data["otp_hash"]
        ):

            otp_data["verified"] = True

            return redirect(url_for("admin_reset_password"))

        otp_data["attempts"] += 1

        if otp_data["attempts"] >= 5:
            ADMIN_OTP_STORE.pop(email, None)
            session.pop("admin_reset_email", None)

            return render_template(
                "admin-verify-otp.html",
                message="Too many incorrect attempts. Request a new OTP."
            )

        return render_template(
            "admin-verify-otp.html",
            message="Incorrect OTP. Please try again."
        )

    return render_template("admin-verify-otp.html")

#ADMIN RESET PASSWORD
@app.route("/admin-reset-password", methods=["GET", "POST"])
def admin_reset_password():

    email = session.get("admin_reset_email")

    if not email or email not in ADMIN_OTP_STORE:
        return redirect(url_for("admin_forgot_password"))

    otp_data = ADMIN_OTP_STORE[email]

    # Check OTP verification and expiry
    if not otp_data.get("verified") or time.time() > otp_data["expires_at"]:
        ADMIN_OTP_STORE.pop(email, None)
        session.pop("admin_reset_email", None)
        return redirect(url_for("admin_forgot_password"))

    if request.method == "POST":

        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(new_password) < 8:
            return render_template(
                "admin-reset-password.html",
                message="Password must contain at least 8 characters."
            )

        if new_password != confirm_password:
            return render_template(
                "admin-reset-password.html",
                message="Passwords do not match."
            )

        # Read admin records
        admins = []

        with open(ADMIN_FILE, "r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames
            admins = list(reader)

        # Update password
        for admin in admins:
            if admin.get("email", "").strip().lower() == email:
                admin["password"] = generate_password_hash(new_password)
                break

        # Save updated records
        with open(ADMIN_FILE, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(admins)

        # Remove used OTP
        ADMIN_OTP_STORE.pop(email, None)
        session.pop("admin_reset_email", None)

        return redirect(url_for("admin_login"))

    return render_template("admin-reset-password.html")


#ADMIN DASHBOARD
@app.route("/admin-dashboard")
def admin_dashboard():

    # Check admin login
    if "admin_email" not in session:
        return redirect("/admin-login")

    # Count registered owners
    total_owners = 0

    if os.path.exists(OWNER_FILE):
        with open(OWNER_FILE, "r", newline="", encoding="utf-8") as file:
            owners = list(csv.DictReader(file))
            total_owners = len(owners)

    # Feedback count (we will connect the actual feedback file later)
    total_feedback = 0

    return render_template(
        "admin-dashboard.html",
        admin_name=session.get("admin_name", "Admin"),
        total_owners=total_owners,
        total_logins=0,
        total_feedback=total_feedback
    )

#ADMIN_PERFORMANCE ROUTE
@app.route("/admin-performance")
def admin_performance():

    if "admin_email" not in session:
        return redirect("/admin-login")

    owners = []

    if os.path.exists(OWNER_FILE):
        with open(OWNER_FILE, "r", newline="", encoding="utf-8") as file:
            owners = list(csv.DictReader(file))

    # Count owners for each company
    company_counts = {
        "Amazon": 0,
        "Flipkart": 0,
        "Myntra": 0,
        "Meesho": 0
    }

    for owner in owners:
        company = owner.get("company", "").strip().title()

        if company in company_counts:
            company_counts[company] += 1

        # Read uploaded filename for this owner
        owner_email = owner.get("email", "").strip().lower()

        if owner_email:
            csv_path = get_owner_csv_path(owner_email)

            filename_path = os.path.join(
                os.path.dirname(csv_path),
                "uploaded_filename.txt"
            )

            owner["uploaded_filename"] = ""

            if os.path.exists(filename_path):
                with open(filename_path, "r", encoding="utf-8") as file:
                    owner["uploaded_filename"] = file.read().strip()

            owner["has_dataset"] = os.path.exists(csv_path)
        else:
            owner["uploaded_filename"] = ""
            owner["has_dataset"] = False

    return render_template(
        "admin-performance.html",
        owners=owners,
        company_counts=company_counts,
        admin_name=session.get("admin_name", "Admin")
    )

#ADMIN CSV FILE VIEW ROUTE
@app.route("/admin-view-owner/<owner_email>")
def admin_view_owner(owner_email):

    if "admin_email" not in session:
        return redirect("/admin-login")


    owner_email = owner_email.strip().lower()

    csv_path = get_owner_csv_path(owner_email)

    if not os.path.exists(csv_path):
        return "Owner CSV file not found."

    with open(csv_path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames or []
        rows = list(reader)

    return render_template(
        "admin-view-owner.html",
        owner_email=owner_email,
        columns=columns,
        rows=rows
    )

#ADMIN-VISITORS ROUTE
@app.route("/admin-visitors")
def admin_visitors():

    # Check admin login
    if "admin_email" not in session:
        return redirect("/admin-login")

    # Read owner registration details
    owners = []
    login_history = []

    if os.path.exists(OWNER_FILE):
        with open(OWNER_FILE, "r", newline="", encoding="utf-8") as file:
            owners = list(csv.DictReader(file))

    # Read owner login history
    if os.path.exists(LOGIN_HISTORY_FILE):
        with open(LOGIN_HISTORY_FILE, "r", newline="", encoding="utf-8") as file:
            login_history = list(csv.DictReader(file))

    # Show newest records first
    owners.reverse()
    login_history.reverse()

    return render_template(
        "admin-visitors.html",
        admin_name=session.get("admin_name", "Admin"),
        total_owners=len(owners),
        owners=owners,
        login_history=login_history
    )

#ADMIN LOGOUT
@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_email", None)
    return redirect("/")


#ADMIN-GRAPHS-ANALYSIS
@app.route('/admin-graphs-analysis')
def admin_graph_analysis():

    # Check admin login
    if not session.get('admin_email'):
        return redirect(url_for('admin_login'))

    # Accuracy CSV path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    accuracy_file = os.path.join(
        base_dir, 'data', 'owner_accuracy.csv'
    )

    owner_names = []
    model_accuracies = []

    # Read saved model accuracy
    if os.path.exists(accuracy_file):
        with open(
            accuracy_file, 'r', newline='', encoding='utf-8-sig'
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:
                try:
                    accuracy = float(
                        row['model_accuracy'].strip().replace('%', '')
                    )

                    if 0 <= accuracy <= 100:
                        owner_names.append(row['owner_name'])
                        model_accuracies.append(accuracy)

                except (ValueError, KeyError, AttributeError):
                    continue

    return render_template(
        'admin-graphs-analysis.html',
        owner_names=owner_names,
        model_accuracies=model_accuracies
    )


#ADMIN-OWNER-MANAGEMENT
@app.route("/admin-owner-management")
def admin_owner_management():

    if "admin_email" not in session:
        return redirect(url_for("admin_login"))

    import csv

    # Read registered owners
    owners = []

    if os.path.exists(OWNER_FILE):
        with open(OWNER_FILE, "r", newline="", encoding="utf-8-sig") as file:
            owners = list(csv.DictReader(file))

    # Read saved model accuracy
    accuracy_rows = []

    if os.path.exists(ACCURACY_FILE):
        with open(ACCURACY_FILE, "r", newline="", encoding="utf-8-sig") as file:
            accuracy_rows = list(csv.DictReader(file))

    # Prepare owner information
    for index, owner in enumerate(owners, start=1):

        owner["si_no"] = index
        owner_email = owner.get("email", "").strip().lower()

        owner["uploaded_file"] = "Not Uploaded"
        owner["model_accuracy"] = "Not Available"
        owner["has_upload"] = False

        # Find owner's uploaded CSV
        try:
            customer_path = get_owner_csv_path(owner_email)

            if os.path.exists(customer_path):
                owner["has_upload"] = True

                filename_path = os.path.join(
                    os.path.dirname(customer_path),
                    "uploaded_filename.txt"
                )

                if os.path.exists(filename_path):
                    with open(filename_path, "r", encoding="utf-8") as file:
                        owner["uploaded_file"] = file.read().strip()

                else:
                    owner["uploaded_file"] = "customer-data.csv"

        except (ValueError, OSError):
            pass

        # Find saved accuracy for this owner
        for accuracy_row in accuracy_rows:

            if (
                accuracy_row.get("owner_name", "").strip().lower()
                == owner.get("owner_name", "").strip().lower()
                and
                accuracy_row.get("company", "").strip().lower()
                == owner.get("company", "").strip().lower()
            ):
                owner["model_accuracy"] = accuracy_row.get(
                    "model_accuracy", "Not Available"
                )
                break

    # Dashboard summary
    total_owners = len(owners)

    uploaded_owners = sum(
        1 for owner in owners if owner["has_upload"]
    )

    accuracy_values = []

    for owner in owners:
        try:
            accuracy_values.append(float(owner["model_accuracy"]))
        except (ValueError, TypeError):
            pass

    average_accuracy = (
        round(sum(accuracy_values) / len(accuracy_values), 2)
        if accuracy_values else 0
    )

    # Select owner when View is clicked
    selected_email = request.args.get("view", "").strip().lower()

    selected_owner = None
    customer_stats = {}
    gender_chart = None

    if selected_email:

        for owner in owners:
            if owner.get("email", "").strip().lower() == selected_email:
                selected_owner = owner
                break

        if selected_owner and selected_owner["has_upload"]:

            customer_path = get_owner_csv_path(selected_email)

            try:
                df = pd.read_csv(customer_path, encoding="utf-8-sig")

                # Standardize column names
                df.columns = [
                    str(column).strip().lower().replace(" ", "_")
                    for column in df.columns
                ]

                # Standardize gender values
                if "gender" in df.columns:
                    df["gender"] = (
                        df["gender"].astype(str).str.strip().str.title()
                    )

                    df["gender"] = df["gender"].replace({
                        "0": "Male",
                        "1": "Female"
                    })

                # Standardize purchase status
                if "purchase_status" in df.columns:

                    status = (
                        df["purchase_status"]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                    )

                    df["purchase_status"] = status.replace({
                        "yes": "Purchase",
                        "purchased": "Purchase",
                        "purchase": "Purchase",
                        "no": "No Purchase",
                        "not purchased": "No Purchase",
                        "not purchase": "No Purchase"
                    })

                total_customers = len(df)

                male_count = (int((df["gender"] == "Male").sum())
                    if "gender" in df.columns else 0
                )

                female_count = (int((df["gender"] == "Female").sum())
                    if "gender" in df.columns else 0
                )

                purchase_count = (
                    int((df["purchase_status"] == "Purchase").sum())
                    if "purchase_status" in df.columns else 0
                )

                purchase_rate = (
                    round((purchase_count / total_customers) * 100, 2)
                    if total_customers else 0
                )

                category_counts = (
                    df["category"].value_counts().to_dict()
                    if "category" in df.columns else {}
                )

                customer_stats = {
                    "total_customers": total_customers,
                    "male_count": male_count,
                    "female_count": female_count,
                    "purchase_rate": purchase_rate,
                    "category_counts": category_counts
                }

                # Gender-wise Purchase / No Purchase graph
                if (
                    "gender" in df.columns
                    and "purchase_status" in df.columns
                ):

                    chart_data = pd.crosstab(
                        df["gender"],
                        df["purchase_status"]
                    )

                    for status_name in ["Purchase", "No Purchase"]:
                        if status_name not in chart_data.columns:
                            chart_data[status_name] = 0

                    chart_data = chart_data[
                        ["Purchase", "No Purchase"]
                    ]

                    fig, ax = plt.subplots(figsize=(7, 4))

                    chart_data.plot(
                        kind="bar",
                        ax=ax,
                        color=["#8B5CF6", "#F97316"]
                    )

                    ax.set_title("Gender-wise Purchase Analysis")
                    ax.set_xlabel("Gender")
                    ax.set_ylabel("Number of Customers")
                    ax.legend(title="Purchase Status")
                    ax.tick_params(axis="x", rotation=0)

                    plt.tight_layout()

                    image_buffer = io.BytesIO()
                    fig.savefig(
                        image_buffer,
                        format="png",
                        bbox_inches="tight"
                    )

                    image_buffer.seek(0)

                    gender_chart = base64.b64encode(
                        image_buffer.getvalue()
                    ).decode("utf-8")

                    plt.close(fig)

            except Exception as error:
                print("Owner dataset analysis error:", error)

    return render_template(
        "admin-owner-management.html",
        owners=owners,
        total_owners=total_owners,
        uploaded_owners=uploaded_owners,
        average_accuracy=average_accuracy,
        selected_owner=selected_owner,
        customer_stats=customer_stats,
        gender_chart=gender_chart
    )


@app.route("/delete-owner/<email>", methods=["POST"])
def delete_owner(email):

    if "admin_email" not in session:
        return redirect(url_for("admin_login"))

    email = email.strip().lower()
    owners = []

    if os.path.exists(OWNER_FILE):
        with open(OWNER_FILE, newline="", encoding="utf-8-sig") as f:
            owners = list(csv.DictReader(f))

    remaining = [
        owner for owner in owners
        if owner.get("email", "").strip().lower() != email
    ]

    if len(remaining) == len(owners):
        return "Owner not found.", 404

    with open(OWNER_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=owners[0].keys()
        )
        writer.writeheader()
        writer.writerows(remaining)

    folder = hashlib.sha256(email.encode("utf-8")).hexdigest()
    owner_folder = os.path.join(DATA_FOLDER, "customers", folder)

    if os.path.isdir(owner_folder):
        shutil.rmtree(owner_folder)

    return redirect(url_for("admin_owner_management"))





#OWNER FORGOT PASSSWORD
@app.route("/owner-forgot-password", methods=["GET", "POST"])
def owner_forgot_password():

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        new_password = request.form.get("new_password", "")

        if not email or not new_password:
            return render_template(
                "owner-forgot.html",
                error="Please enter your email and new password."
            )

        if len(new_password) < 8:
            return render_template(
                "owner-forgot.html",
                error="Password must contain at least 8 characters."
            )

        if not os.path.exists(OWNER_FILE):
            return render_template(
                "owner-forgot.html",
                error="Owner account not found."
            )

        with open(OWNER_FILE, "r", newline="", encoding="utf-8-sig") as file:
            owners = list(csv.DictReader(file))

        owner_found = False

        for owner in owners:
            if owner["email"].strip().lower() == email:
                owner["password_hash"] = generate_password_hash(new_password)
                owner_found = True
                break

        if not owner_found:
            return render_template(
                "owner-forgot.html",
                error="Email not registered."
            )

        with open(OWNER_FILE, "w", newline="", encoding="utf-8") as file:
            fieldnames = ["owner_name", "company", "email", "password_hash"]

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
                extrasaction="ignore"
            )

            writer.writeheader()

            for owner in owners:
                clean_owner = {
                    field: owner.get(field, "")
                    for field in fieldnames
                }
                writer.writerow(clean_owner)
                
        return render_template(
            "owner-forgot.html",
            message="Password reset successful! You can now log in."
        )

    return render_template("owner-forgot.html")



if __name__ == "__main__":
    print("Smart Buy website is starting...")
    app.run(debug=True)