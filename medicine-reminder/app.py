
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date
import sqlite3

app = Flask(__name__)
app.secret_key = "bloomcare-secret-key"


# Connect to the database
def get_db():
    conn = sqlite3.connect("medicines.db")
    conn.row_factory = sqlite3.Row
    return conn


# Create the table and add the stock column if needed
def create_table():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            expiry TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Add quantity to older databases that don't have it yet
    columns = conn.execute(
        "PRAGMA table_info(medicines)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "quantity" not in column_names:
        conn.execute("""
            ALTER TABLE medicines
            ADD COLUMN quantity INTEGER NOT NULL DEFAULT 0
        """)

    conn.commit()
    conn.close()


# Check medicine expiry status
def get_status(expiry_date):
    expiry = date.fromisoformat(expiry_date)
    today = date.today()

    if expiry < today:
        return "Expired"
    elif (expiry - today).days <= 30:
        return "Expiring Soon"
    else:
        return "Not Expired"


# Check if a medicine expires within 7 days
def expires_within_7_days(expiry_date):
    expiry = date.fromisoformat(expiry_date)
    days_left = (expiry - date.today()).days

    return 0 <= days_left <= 7


# Overview page
@app.route("/")
def home():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM medicines ORDER BY id DESC"
    ).fetchall()
    conn.close()

    medicines = []

    for row in rows:
        medicines.append({
            "id": row["id"],
            "name": row["name"],
            "expiry": row["expiry"],
            "quantity": row["quantity"],
            "status": get_status(row["expiry"]),
            "urgent": expires_within_7_days(row["expiry"])
        })

    return render_template("index.html", medicines=medicines)


# Add a new medicine
@app.route("/add", methods=["POST"])
def add_medicine():
    medicine_name = request.form["medicine_name"].strip()
    expiry_date = request.form["expiry_date"]

    conn = get_db()
    conn.execute(
        "INSERT INTO medicines (name, expiry, quantity) VALUES (?, ?, ?)",
        (medicine_name, expiry_date, 0)
    )
    conn.commit()
    conn.close()

    return redirect("/")


# Edit a medicine
@app.route("/edit/<int:medicine_id>", methods=["GET", "POST"])
def edit_medicine(medicine_id):
    conn = get_db()

    if request.method == "POST":
        medicine_name = request.form["medicine_name"].strip()
        expiry_date = request.form["expiry_date"]

        conn.execute(
            "UPDATE medicines SET name = ?, expiry = ? WHERE id = ?",
            (medicine_name, expiry_date, medicine_id)
        )
        conn.commit()
        conn.close()

        return redirect("/")

    medicine = conn.execute(
        "SELECT * FROM medicines WHERE id = ?",
        (medicine_id,)
    ).fetchone()

    conn.close()

    if medicine is None:
        return redirect("/")

    return render_template("edit.html", medicine=medicine)


# Delete a medicine
@app.route("/delete/<int:medicine_id>", methods=["POST"])
def delete_medicine(medicine_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM medicines WHERE id = ?",
        (medicine_id,)
    )
    conn.commit()
    conn.close()

    return redirect("/")


# Stock management page
@app.route("/stock")
def stock():
    conn = get_db()

    medicines = conn.execute("""
        SELECT * FROM medicines
        ORDER BY name ASC
    """).fetchall()

    total_units = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM medicines"
    ).fetchone()[0]

    low_stock = conn.execute("""
        SELECT COUNT(*) FROM medicines
        WHERE quantity > 0 AND quantity <= 10
    """).fetchone()[0]

    out_of_stock = conn.execute("""
        SELECT COUNT(*) FROM medicines
        WHERE quantity = 0
    """).fetchone()[0]

    conn.close()

    return render_template(
        "stock.html",
        medicines=medicines,
        total_units=total_units,
        low_stock=low_stock,
        out_of_stock=out_of_stock
    )


# Add more stock
@app.route("/stock/add/<int:medicine_id>", methods=["POST"])
def add_stock(medicine_id):
    quantity = request.form.get("quantity", type=int)

    if quantity is None or quantity <= 0:
        flash("Enter a quantity greater than zero.")
        return redirect(url_for("stock"))

    conn = get_db()

    medicine = conn.execute(
        "SELECT id FROM medicines WHERE id = ?",
        (medicine_id,)
    ).fetchone()

    if medicine:
        conn.execute(
            "UPDATE medicines SET quantity = quantity + ? WHERE id = ?",
            (quantity, medicine_id)
        )
        conn.commit()
        flash("Stock added successfully.")
    else:
        flash("Medicine not found.")

    conn.close()
    return redirect(url_for("stock"))


# Sell or issue medicine
@app.route("/stock/issue/<int:medicine_id>", methods=["POST"])
def issue_stock(medicine_id):
    quantity = request.form.get("quantity", type=int)

    if quantity is None or quantity <= 0:
        flash("Enter a quantity greater than zero.")
        return redirect(url_for("stock"))

    conn = get_db()

    medicine = conn.execute(
        "SELECT quantity FROM medicines WHERE id = ?",
        (medicine_id,)
    ).fetchone()

    if medicine is None:
        flash("Medicine not found.")
    elif quantity > medicine["quantity"]:
        flash("Not enough stock available.")
    else:
        conn.execute(
            "UPDATE medicines SET quantity = quantity - ? WHERE id = ?",
            (quantity, medicine_id)
        )
        conn.commit()
        flash("Stock issued or sold successfully.")

    conn.close()
    return redirect(url_for("stock"))


# Create the database when the application starts
create_table()


if __name__ == "__main__":
    app.run(debug=True)
