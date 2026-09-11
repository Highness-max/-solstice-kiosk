# app.py - Reflex: Delivery Management System (Async + Webhooks + SSE)
from flask import Flask, request, jsonify, render_template_string, Response, stream_with_context
import datetime
import json
import uuid
import time
import threading
import os

app = Flask(__name__)

# ---------- IN-MEMORY "DATABASE" ----------
# In production, this would be PostgreSQL/SQLite.
# For this prototype, we use Python dictionaries.

# Delivery requests
deliveries = {
    "DEL-001": {
        "id": "DEL-001",
        "customer_name": "Alice Wanjiru",
        "customer_phone": "+254-700-000-001",
        "delivery_address": "Karen, Nairobi",
        "item_description": 'Samsung 55" Smart TV',
        "status": "Requested",
        "assigned_rider": None,
        "assigned_rider_name": None,
        "created_by": "retailer-001",
        "created_at": "2026-09-10T08:30:00",
        "assigned_at": None,
        "picked_up_at": None,
        "delivered_at": None,
        "proof_of_delivery": None
    },
    "DEL-002": {
        "id": "DEL-002",
        "customer_name": "Brian Ochieng",
        "customer_phone": "+254-700-000-002",
        "delivery_address": "Westlands, Nairobi",
        "item_description": "HP Laptop Charger",
        "status": "Requested",
        "assigned_rider": None,
        "assigned_rider_name": None,
        "created_by": "retailer-001",
        "created_at": "2026-09-10T08:45:00",
        "assigned_at": None,
        "picked_up_at": None,
        "delivered_at": None,
        "proof_of_delivery": None
    }
}

# Riders (delivery personnel)
riders = {
    "RDR-001": {"id": "RDR-001", "name": "John Mwangi", "phone": "+254-700-000-101", "active_deliveries": 0},
    "RDR-002": {"id": "RDR-002", "name": "Mary Njeri", "phone": "+254-700-000-102", "active_deliveries": 0},
    "RDR-003": {"id": "RDR-003", "name": "Peter Kamau", "phone": "+254-700-000-103", "active_deliveries": 0}
}

# ---------- MESSAGE QUEUE ----------
assignment_queue = []
completed_jobs = []
assigned_deliveries = set()
queue_worker_started = False


# ---------- WORKER: PROCESSES THE QUEUE ----------
def process_assignment_queue():
    """Background worker that processes queued jobs."""
    print("🔄 Reflex queue worker thread started and is now running!")
    while True:
        try:
            if assignment_queue:
                job = assignment_queue.pop(0)
                print(f"📊 Queue has {len(assignment_queue)} remaining. Processing job: {job['type']}")

                time.sleep(3)

                completed_jobs.append({
                    "job_id": job["job_id"],
                    "type": job["type"],
                    "delivery_id": job["delivery_id"],
                    "status": "completed",
                    "timestamp": str(datetime.datetime.now())
                })

                print(f"✅ Job {job['job_id']} processed. Calling webhook...")
                process_webhook_callback(job)
            else:
                time.sleep(1)
        except Exception as e:
            print(f"❌ Queue worker error: {e}")
            time.sleep(5)


def process_webhook_callback(job):
    """Simulates the rider's mobile app calling our webhook with confirmation."""
    print(f"📡 Webhook callback for job {job['job_id']} ({job['type']})...")
    time.sleep(2)

    with app.app_context():
        try:
            delivery_id = job["delivery_id"]
            delivery = deliveries.get(delivery_id)
            if not delivery:
                print(f"❌ Delivery {delivery_id} not found")
                return

            job_type = job["type"]
            now = str(datetime.datetime.now())

            if job_type == "assign_rider":
                delivery["status"] = "Assigned"
                delivery["assigned_rider"] = job["rider_id"]
                delivery["assigned_rider_name"] = riders[job["rider_id"]]["name"]
                delivery["assigned_at"] = now
                riders[job["rider_id"]]["active_deliveries"] += 1
                print(f"✅ {delivery_id} assigned to {delivery['assigned_rider_name']}")

            elif job_type == "mark_picked_up":
                delivery["status"] = "Picked Up"
                delivery["picked_up_at"] = now
                print(f"✅ {delivery_id} marked as Picked Up")

            elif job_type == "mark_delivered":
                delivery["status"] = "Delivered"
                delivery["delivered_at"] = now
                delivery["proof_of_delivery"] = job.get("proof", "Signed by customer")
                if delivery["assigned_rider"]:
                    riders[delivery["assigned_rider"]]["active_deliveries"] = max(
                        0, riders[delivery["assigned_rider"]]["active_deliveries"] - 1
                    )
                print(f"✅ {delivery_id} marked as Delivered")

            assigned_deliveries.discard(delivery_id)

        except Exception as e:
            print(f"❌ Webhook processing failed: {e}")


# ---------- FLASK ROUTES ----------

@app.route('/')
def index():
    """Serve the Reflex UI"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/deliveries', methods=['GET'])
def get_deliveries():
    return jsonify(deliveries)


@app.route('/api/riders', methods=['GET'])
def get_riders():
    return jsonify(riders)


@app.route('/api/deliveries', methods=['POST'])
def create_delivery():
    """RETAILER: Log a new delivery request."""
    data = request.get_json(silent=True) or {}

    customer_name = str(data.get('customer_name', '')).strip()
    customer_phone = str(data.get('customer_phone', '')).strip()
    delivery_address = str(data.get('delivery_address', '')).strip()
    item_description = str(data.get('item_description', '')).strip()

    if not all([customer_name, customer_phone, delivery_address, item_description]):
        return jsonify({
            "error": "Missing required fields",
            "required": ["customer_name", "customer_phone", "delivery_address", "item_description"]
        }), 400

    delivery_id = f"DEL-{uuid.uuid4().hex[:6].upper()}"

    deliveries[delivery_id] = {
        "id": delivery_id,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "delivery_address": delivery_address,
        "item_description": item_description,
        "status": "Requested",
        "assigned_rider": None,
        "assigned_rider_name": None,
        "created_by": "retailer-001",
        "created_at": str(datetime.datetime.now()),
        "assigned_at": None,
        "picked_up_at": None,
        "delivered_at": None,
        "proof_of_delivery": None
    }

    print(f"📦 New delivery request: {delivery_id} for {customer_name}")

    return jsonify({
        "status": "created",
        "message": f"Delivery request {delivery_id} logged for {customer_name}",
        "delivery_id": delivery_id,
        "delivery": deliveries[delivery_id]
    }), 201


@app.route('/api/assign', methods=['POST'])
def assign_rider():
    """DISPATCHER: Assign a delivery to a rider."""
    data = request.get_json(silent=True) or {}
    delivery_id = str(data.get('delivery_id', '')).strip()
    rider_id = str(data.get('rider_id', '')).strip()

    if not delivery_id or not rider_id:
        return jsonify({"error": "delivery_id and rider_id are required"}), 400

    if delivery_id not in deliveries:
        return jsonify({"error": "Delivery not found"}), 404

    if rider_id not in riders:
        return jsonify({"error": "Rider not found"}), 404

    delivery = deliveries[delivery_id]

    if delivery_id in assigned_deliveries:
        return jsonify({
            "error": "Already assigned",
            "message": f"{delivery_id} has already been assigned to a rider.",
            "status": "duplicate"
        }), 409

    if delivery["status"] != "Requested":
        return jsonify({
            "error": "Invalid state",
            "message": f"Cannot assign delivery in '{delivery['status']}' state.",
            "status": "invalid_state"
        }), 409

    assigned_deliveries.add(delivery_id)

    job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
    assignment_queue.append({
        "job_id": job_id,
        "type": "assign_rider",
        "delivery_id": delivery_id,
        "rider_id": rider_id,
        "published_at": str(datetime.datetime.now())
    })

    return jsonify({
        "status": "pending",
        "message": f"Assigning {delivery_id} to {riders[rider_id]['name']}. Waiting for rider confirmation...",
        "job_id": job_id,
        "delivery_id": delivery_id,
        "rider_id": rider_id,
        "queue_position": len(assignment_queue)
    }), 202


@app.route('/api/rider/update', methods=['POST'])
def rider_update_status():
    """RIDER: Update delivery status (Picked Up / Delivered)."""
    data = request.get_json(silent=True) or {}
    delivery_id = str(data.get('delivery_id', '')).strip()
    new_status = str(data.get('new_status', '')).strip()
    rider_id = str(data.get('rider_id', '')).strip()

    if not delivery_id or not new_status:
        return jsonify({"error": "delivery_id and new_status are required"}), 400

    if delivery_id not in deliveries:
        return jsonify({"error": "Delivery not found"}), 404

    delivery = deliveries[delivery_id]

    if rider_id and delivery["assigned_rider"] != rider_id:
        return jsonify({"error": "This delivery is not assigned to you"}), 403

    valid_transitions = {
        "Picked Up": "Assigned",
        "Delivered": "Picked Up"
    }

    if new_status not in valid_transitions:
        return jsonify({"error": f"Invalid target status: {new_status}"}), 400

    required_current = valid_transitions[new_status]
    if delivery["status"] != required_current:
        return jsonify({
            "error": "Invalid transition",
            "message": f"Cannot transition from '{delivery['status']}' to '{new_status}'. Must be '{required_current}' first."
        }), 409

    job_type = "mark_picked_up" if new_status == "Picked Up" else "mark_delivered"
    job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"

    job = {
        "job_id": job_id,
        "type": job_type,
        "delivery_id": delivery_id,
        "rider_id": rider_id,
        "published_at": str(datetime.datetime.now())
    }

    if job_type == "mark_delivered":
        job["proof"] = data.get("proof", "Signed by customer")

    assignment_queue.append(job)

    return jsonify({
        "status": "pending",
        "message": f"Updating {delivery_id} to '{new_status}'. Waiting for confirmation...",
        "job_id": job_id,
        "queue_position": len(assignment_queue)
    }), 202


@app.route('/api/scan/<delivery_id>', methods=['GET'])
def scan_qr(delivery_id):
    """SCAN: Look up a delivery by QR code / ID."""
    if delivery_id not in deliveries:
        return jsonify({"error": "Delivery not found"}), 404

    delivery = deliveries[delivery_id]

    proof = None
    if delivery["status"] == "Delivered":
        proof = {
            "delivered_at": delivery["delivered_at"],
            "proof_of_delivery": delivery["proof_of_delivery"],
            "rider": delivery["assigned_rider_name"]
        }

    return jsonify({
        "delivery": delivery,
        "proof_of_delivery": proof,
        "verified": delivery["status"] == "Delivered"
    })


@app.route('/webhook/rider-confirm', methods=['POST'])
def rider_confirm_webhook():
    """WEBHOOK: Rider app calls back to confirm a status change."""
    data = request.get_json(silent=True) or {}
    print(f"📩 Webhook received: {data}")

    delivery_id = data.get("delivery_id")
    if not delivery_id or delivery_id not in deliveries:
        return jsonify({"error": "Invalid delivery ID"}), 400

    delivery = deliveries[delivery_id]
    new_status = data.get("status")

    if new_status == "Assigned":
        delivery["status"] = "Assigned"
    elif new_status == "Picked Up":
        delivery["status"] = "Picked Up"
    elif new_status == "Delivered":
        delivery["status"] = "Delivered"

    return jsonify({"status": "success", "message": "Webhook processed"}), 200


@app.route('/api/queue', methods=['GET'])
def get_queue_status():
    return jsonify({
        "queue_length": len(assignment_queue),
        "pending_jobs": assignment_queue,
        "completed_jobs": completed_jobs[-10:]
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    status_counts = {"Requested": 0, "Assigned": 0, "Picked Up": 0, "Delivered": 0}
    for d in deliveries.values():
        status_counts[d["status"]] = status_counts.get(d["status"], 0) + 1

    return jsonify({
        "total_deliveries": len(deliveries),
        "by_status": status_counts,
        "total_riders": len(riders),
        "active_riders": sum(1 for r in riders.values() if r["active_deliveries"] > 0)
    })


# ---------- SERVER-SENT EVENTS (REAL-TIME UPDATES) ----------
@app.route('/api/stream')
def event_stream():
    """SSE endpoint for real-time UI updates"""
    def generate():
        last_snapshot = ""
        while True:
            try:
                time.sleep(1)

                snapshot = json.dumps({
                    "deliveries": {d_id: d["status"] for d_id, d in deliveries.items()},
                    "queue_len": len(assignment_queue)
                })

                if snapshot != last_snapshot:
                    last_snapshot = snapshot
                    yield f"data: {json.dumps({'action': 'refresh'})}\n\n"

            except GeneratorExit:
                print("🔴 SSE client disconnected")
                break
            except Exception as e:
                print(f"⚠️ SSE error: {e}")
                break

    return Response(generate(), mimetype="text/event-stream")


# ---------- START WORKER ON IMPORT ----------
def start_queue_worker():
    global queue_worker_started
    if queue_worker_started:
        return
    worker_thread = threading.Thread(target=process_assignment_queue, daemon=True)
    worker_thread.start()
    queue_worker_started = True
    print("🚀 Reflex queue worker started!")


start_queue_worker()


# ---------- HTML TEMPLATE (Reflex UI with 3 Tabs) ----------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Reflex · Delivery Management</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" />
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f6f8fc;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 30px;
            background: #0a1628;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        }
        .header h1 { color: #ffffff; font-size: 2.2rem; }
        .header h1 i { color: #d4af37; margin-right: 12px; }
        .header p { color: #b0c4d8; margin-top: 6px; }
        .badge-status {
            display: inline-block;
            background: #d4af37;
            color: #0a1628;
            padding: 4px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.8rem;
            margin-top: 10px;
        }

        .tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
            background: #ffffff;
            padding: 8px;
            border-radius: 16px;
            box-shadow: 0 4px 12px rgba(10,25,47,0.05);
        }
        .tab {
            flex: 1;
            padding: 14px 20px;
            border: none;
            background: transparent;
            border-radius: 12px;
            font-weight: 600;
            font-size: 0.95rem;
            color: #6b7f94;
            cursor: pointer;
            transition: 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .tab:hover { background: #f0f4fe; }
        .tab.active {
            background: #0a1628;
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(10,25,47,0.2);
        }
        .tab.active i { color: #d4af37; }

        .panel { display: none; }
        .panel.active { display: block; }

        .card {
            background: #ffffff;
            border-radius: 18px;
            padding: 28px;
            box-shadow: 0 4px 12px rgba(10,25,47,0.06);
            margin-bottom: 20px;
            border-top: 4px solid #d4af37;
        }
        .card h2 {
            color: #0a1628;
            font-size: 1.3rem;
            margin-bottom: 18px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .card h2 i { color: #d4af37; }

        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin-bottom: 16px;
        }
        .form-grid .full { grid-column: 1 / -1; }
        label {
            display: block;
            font-weight: 600;
            color: #0a1628;
            margin-bottom: 6px;
            font-size: 0.85rem;
        }
        input, textarea, select {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 12px;
            font-size: 0.95rem;
            font-family: inherit;
            background: #fafcff;
            transition: 0.2s;
        }
        input:focus, textarea:focus, select:focus {
            border-color: #d4af37;
            outline: none;
            background: #ffffff;
        }
        textarea { resize: vertical; min-height: 70px; }

        .btn {
            background: #0a1628;
            color: #ffffff;
            border: none;
            padding: 14px 28px;
            border-radius: 40px;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            transition: 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-family: inherit;
        }
        .btn:hover { background: #1a2b4c; transform: scale(1.02); }
        .btn:active { transform: scale(0.97); }
        .btn-gold { background: #d4af37; color: #0a1628; }
        .btn-gold:hover { background: #c19c2b; }
        .btn-small {
            padding: 8px 16px;
            font-size: 0.8rem;
            border-radius: 20px;
        }

        .delivery-item {
            background: #f8fafd;
            border-radius: 14px;
            padding: 16px 20px;
            margin-bottom: 12px;
            border-left: 4px solid #d4af37;
            transition: 0.2s;
        }
        .delivery-item:hover { background: #f0f4fe; }
        .delivery-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .delivery-id {
            font-family: monospace;
            font-weight: 700;
            color: #0a1628;
            font-size: 1rem;
        }
        .status-badge {
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        .status-requested { background: #fff3cd; color: #856404; }
        .status-assigned { background: #cce5ff; color: #004085; }
        .status-picked-up { background: #e2d4f7; color: #4b2e83; }
        .status-delivered { background: #d4edda; color: #155724; }

        .delivery-details {
            font-size: 0.88rem;
            color: #4a5b6c;
            line-height: 1.6;
        }
        .delivery-details strong { color: #0a1628; }
        .delivery-actions {
            margin-top: 12px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }
        .rider-select {
            padding: 8px 14px;
            border: 2px solid #e2e8f0;
            border-radius: 20px;
            font-size: 0.85rem;
            background: #ffffff;
            cursor: pointer;
            font-family: inherit;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: #ffffff;
            padding: 16px;
            border-radius: 14px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(10,25,47,0.05);
        }
        .stat-number {
            font-size: 1.8rem;
            font-weight: 700;
            color: #0a1628;
        }
        .stat-label {
            font-size: 0.75rem;
            color: #6b7f94;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 4px;
        }

        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: #8a9baa;
        }
        .empty-state i { font-size: 3rem; color: #d4e0ec; margin-bottom: 12px; }

        .footer {
            text-align: center;
            margin-top: 30px;
            padding: 20px;
            color: #8a9baa;
            font-size: 0.85rem;
        }

        @media (max-width: 700px) {
            .form-grid { grid-template-columns: 1fr; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .tab { font-size: 0.8rem; padding: 12px 10px; }
            .header h1 { font-size: 1.6rem; }
        }
    </style>
</head>
<body>

<div class="container">

    <div class="header">
        <h1><i class="fas fa-truck-fast"></i> Reflex</h1>
        <p>Delivery Management for Kenyan Retailers</p>
        <span class="badge-status"><i class="fas fa-bolt"></i> Real-Time · Async · Proof of Delivery</span>
    </div>

    <div class="tabs">
        <button class="tab active" onclick="switchTab('retailer', this)">
            <i class="fas fa-store"></i> Retailer
        </button>
        <button class="tab" onclick="switchTab('dispatcher', this)">
            <i class="fas fa-user-tie"></i> Dispatcher
        </button>
        <button class="tab" onclick="switchTab('rider', this)">
            <i class="fas fa-motorcycle"></i> Rider
        </button>
    </div>

    <!-- RETAILER PANEL -->
    <div id="panel-retailer" class="panel active">
        <div class="card">
            <h2><i class="fas fa-plus-circle"></i> Log a New Delivery Request</h2>
            <div class="form-grid">
                <div>
                    <label>Customer Name</label>
                    <input type="text" id="customerName" placeholder="e.g. Alice Wanjiru" />
                </div>
                <div>
                    <label>Customer Phone</label>
                    <input type="text" id="customerPhone" placeholder="+254-700-000-000" />
                </div>
                <div class="full">
                    <label>Delivery Address</label>
                    <input type="text" id="deliveryAddress" placeholder="e.g. Karen, Nairobi" />
                </div>
                <div class="full">
                    <label>Item Description</label>
                    <textarea id="itemDescription" placeholder='e.g. Samsung 55" Smart TV'></textarea>
                </div>
            </div>
            <button class="btn" onclick="logDelivery()">
                <i class="fas fa-paper-plane"></i> Submit Delivery Request
            </button>
            <div id="retailerResult" style="margin-top:16px;"></div>
        </div>

        <div class="card">
            <h2><i class="fas fa-list"></i> Your Deliveries (Real-Time Status)</h2>
            <div id="retailerDeliveries"></div>
        </div>

        <div class="card">
            <h2><i class="fas fa-qrcode"></i> Scan QR to Verify Delivery</h2>
            <div style="display:flex;gap:10px;flex-wrap:wrap;">
                <input type="text" id="scanInput" placeholder="Enter Delivery ID (e.g. DEL-001)" style="flex:1;min-width:200px;" />
                <button class="btn btn-gold" onclick="scanQR()">
                    <i class="fas fa-search"></i> Verify
                </button>
            </div>
            <div id="scanResult" style="margin-top:16px;"></div>
        </div>
    </div>

    <!-- DISPATCHER PANEL -->
    <div id="panel-dispatcher" class="panel">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number" id="statTotal">0</div>
                <div class="stat-label">Total</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="statRequested">0</div>
                <div class="stat-label">Requested</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="statAssigned">0</div>
                <div class="stat-label">Assigned</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="statDelivered">0</div>
                <div class="stat-label">Delivered</div>
            </div>
        </div>

        <div class="card">
            <h2><i class="fas fa-tasks"></i> Open Delivery Requests</h2>
            <div id="dispatcherDeliveries"></div>
        </div>

        <div class="card">
            <h2><i class="fas fa-users"></i> Available Riders</h2>
            <div id="ridersList"></div>
        </div>
    </div>

    <!-- RIDER PANEL -->
    <div id="panel-rider" class="panel">
        <div class="card">
            <h2><i class="fas fa-motorcycle"></i> My Assigned Deliveries</h2>
            <label>Select your Rider ID:</label>
            <select id="riderSelect" onchange="loadRiderDeliveries()" style="margin-bottom:16px;">
                <option value="">-- Select Rider --</option>
            </select>
            <div id="riderDeliveries"></div>
        </div>
    </div>

    <div class="footer">
        <i class="fas fa-bolt" style="color:#d4af37;"></i> Reflex · Async Event-Driven Architecture · Built for Kenya
    </div>
</div>

<script>
    let currentTab = 'retailer';

    // ---------- GLOBAL FLAG TO PAUSE POLLING DURING USER INTERACTION ----------
    let pollingPaused = false;

    function switchTab(tabName, btn) {
        currentTab = tabName;
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('panel-' + tabName).classList.add('active');
        loadAll();
    }

    // ---------- RETAILER ----------
    async function logDelivery() {
        const customer_name = document.getElementById('customerName').value.trim();
        const customer_phone = document.getElementById('customerPhone').value.trim();
        const delivery_address = document.getElementById('deliveryAddress').value.trim();
        const item_description = document.getElementById('itemDescription').value.trim();
        const resultDiv = document.getElementById('retailerResult');

        if (!customer_name || !customer_phone || !delivery_address || !item_description) {
            resultDiv.innerHTML = `<div style="color:#c0392b;"><i class="fas fa-exclamation-triangle"></i> All fields are required.</div>`;
            return;
        }

        resultDiv.innerHTML = `<i class="fas fa-spinner fa-pulse" style="color:#d4af37;"></i> Submitting...`;

        try {
            const res = await fetch('/api/deliveries', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ customer_name, customer_phone, delivery_address, item_description })
            });
            const data = await res.json();

            if (res.ok) {
                resultDiv.innerHTML = `
                    <div style="color:#1a7d4a;background:#d4edda;padding:14px 18px;border-radius:12px;">
                        <strong>✅ ${data.message}</strong><br>
                        <small>Delivery ID: <code>${data.delivery_id}</code></small>
                    </div>
                `;
                document.getElementById('customerName').value = '';
                document.getElementById('customerPhone').value = '';
                document.getElementById('deliveryAddress').value = '';
                document.getElementById('itemDescription').value = '';
                loadAll();
            } else {
                resultDiv.innerHTML = `<div style="color:#c0392b;">${data.error}</div>`;
            }
        } catch (e) {
            resultDiv.innerHTML = `<div style="color:#c0392b;">Network error: ${e.message}</div>`;
        }
    }

    async function scanQR() {
        const id = document.getElementById('scanInput').value.trim().toUpperCase();
        const resultDiv = document.getElementById('scanResult');
        if (!id) {
            resultDiv.innerHTML = `<div style="color:#c0392b;">Please enter a Delivery ID</div>`;
            return;
        }

        try {
            const res = await fetch('/api/scan/' + id);
            const data = await res.json();

            if (!res.ok) {
                resultDiv.innerHTML = `<div style="color:#c0392b;">${data.error}</div>`;
                return;
            }

            const d = data.delivery;
            const proof = data.proof_of_delivery;

            resultDiv.innerHTML = `
                <div style="background:#f8fafd;padding:18px;border-radius:14px;border-left:4px solid #d4af37;">
                    <div style="font-weight:700;color:#0a1628;margin-bottom:8px;">${d.id} — ${d.customer_name}</div>
                    <div style="font-size:0.9rem;color:#4a5b6c;">
                        <strong>Item:</strong> ${d.item_description}<br>
                        <strong>Address:</strong> ${d.delivery_address}<br>
                        <strong>Status:</strong> ${d.status}<br>
                        ${d.assigned_rider_name ? `<strong>Rider:</strong> ${d.assigned_rider_name}<br>` : ''}
                    </div>
                    ${proof ? `
                        <div style="margin-top:12px;background:#d4edda;padding:12px;border-radius:10px;">
                            <strong style="color:#155724;">✅ Proof of Delivery</strong><br>
                            <small>Delivered at: ${proof.delivered_at}<br>
                            Proof: ${proof.proof_of_delivery}<br>
                            Rider: ${proof.rider}</small>
                        </div>
                    ` : `<div style="margin-top:12px;color:#8a6d3b;"><i class="fas fa-clock"></i> Not yet delivered</div>`}
                </div>
            `;
        } catch (e) {
            resultDiv.innerHTML = `<div style="color:#c0392b;">Error: ${e.message}</div>`;
        }
    }

    // ---------- DISPATCHER ----------
    async function assignDelivery(deliveryId, riderId) {
        if (!riderId) {
            alert('Please select a rider first');
            return;
        }
        try {
            const res = await fetch('/api/assign', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ delivery_id: deliveryId, rider_id: riderId })
            });
            const data = await res.json();
            if (!res.ok) {
                alert(data.error || data.message);
                return;
            }
            loadAll();
            setTimeout(loadAll, 3000);
            setTimeout(loadAll, 5000);
            setTimeout(loadAll, 8000);
        } catch (e) { alert('Network error: ' + e.message); }
    }

    // ---------- RIDER ----------
    async function updateRiderStatus(deliveryId, newStatus) {
        const riderId = document.getElementById('riderSelect').value;
        if (!riderId) { alert('Select a rider first'); return; }
        try {
            const res = await fetch('/api/rider/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ delivery_id: deliveryId, new_status: newStatus, rider_id: riderId })
            });
            const data = await res.json();
            if (!res.ok) {
                alert(data.error || data.message);
                return;
            }
            loadAll();
            setTimeout(loadAll, 3000);
            setTimeout(loadAll, 5000);
            setTimeout(loadAll, 8000);
        } catch (e) { alert('Network error: ' + e.message); }
    }

    // ---------- DATA LOADING ----------
    async function loadAll() {
        try {
            const [dRes, rRes, sRes] = await Promise.all([
                fetch('/api/deliveries'),
                fetch('/api/riders'),
                fetch('/api/stats')
            ]);
            const deliveries = await dRes.json();
            const riders = await rRes.json();
            const stats = await sRes.json();

            renderRetailerDeliveries(deliveries);
            renderDispatcherDeliveries(deliveries, riders);
            renderRiders(riders);
            updateStats(stats);
            populateRiderSelect(riders);
            loadRiderDeliveries();
        } catch (e) { console.error('Load error:', e); }
    }

    function statusBadge(status) {
        const cls = {
            'Requested': 'status-requested',
            'Assigned': 'status-assigned',
            'Picked Up': 'status-picked-up',
            'Delivered': 'status-delivered'
        }[status] || 'status-requested';
        return `<span class="status-badge ${cls}">${status}</span>`;
    }

    function renderRetailerDeliveries(deliveries) {
        const container = document.getElementById('retailerDeliveries');
        const list = Object.values(deliveries).sort((a, b) => b.created_at.localeCompare(a.created_at));

        if (!list.length) {
            container.innerHTML = `<div class="empty-state"><i class="fas fa-box-open"></i><p>No deliveries yet. Log one above.</p></div>`;
            return;
        }

        container.innerHTML = list.map(d => `
            <div class="delivery-item">
                <div class="delivery-header">
                    <span class="delivery-id">${d.id}</span>
                    ${statusBadge(d.status)}
                </div>
                <div class="delivery-details">
                    <strong>${d.customer_name}</strong> · ${d.customer_phone}<br>
                    📍 ${d.delivery_address}<br>
                    📦 ${d.item_description}
                    ${d.assigned_rider_name ? `<br>🏍️ Rider: <strong>${d.assigned_rider_name}</strong>` : ''}
                    ${d.delivered_at ? `<br>✅ Delivered: ${d.delivered_at}` : ''}
                </div>
            </div>
        `).join('');
    }

    // ---------- DISPATCHER: PRESERVES DROPDOWN SELECTION ----------
    function renderDispatcherDeliveries(deliveries, riders) {
        const container = document.getElementById('dispatcherDeliveries');

        // ---- SAVE CURRENT DROPDOWN SELECTIONS ----
        const savedSelections = {};
        document.querySelectorAll('[id^="rider-DEL-"]').forEach(el => {
            if (el.value) savedSelections[el.id] = el.value;
        });

        const list = Object.values(deliveries).sort((a, b) => b.created_at.localeCompare(a.created_at));

        if (!list.length) {
            container.innerHTML = `<div class="empty-state"><i class="fas fa-inbox"></i><p>No deliveries yet.</p></div>`;
            return;
        }

        container.innerHTML = list.map(d => {
            const riderOptions = Object.values(riders)
                .map(r => `<option value="${r.id}">${r.name} (${r.active_deliveries} active)</option>`)
                .join('');

            return `
                <div class="delivery-item">
                    <div class="delivery-header">
                        <span class="delivery-id">${d.id}</span>
                        ${statusBadge(d.status)}
                    </div>
                    <div class="delivery-details">
                        <strong>${d.customer_name}</strong> · ${d.customer_phone}<br>
                        📍 ${d.delivery_address}<br>
                        📦 ${d.item_description}
                        ${d.assigned_rider_name ? `<br>🏍️ Assigned to <strong>${d.assigned_rider_name}</strong>` : ''}
                    </div>
                    ${d.status === 'Requested' ? `
                        <div class="delivery-actions">
                            <select class="rider-select" id="rider-${d.id}">
                                <option value="">-- Assign to rider --</option>
                                ${riderOptions}
                            </select>
                            <button class="btn btn-small btn-gold" onclick="assignDelivery('${d.id}', document.getElementById('rider-${d.id}').value)">
                                <i class="fas fa-paper-plane"></i> Assign
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

        // ---- RESTORE DROPDOWN SELECTIONS ----
        Object.entries(savedSelections).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el) el.value = value;
        });
    }

    function renderRiders(riders) {
        const container = document.getElementById('ridersList');
        container.innerHTML = Object.values(riders).map(r => `
            <div class="delivery-item" style="border-left-color:#0a1628;">
                <div class="delivery-header">
                    <span class="delivery-id">${r.name}</span>
                    <span class="status-badge ${r.active_deliveries > 0 ? 'status-assigned' : 'status-delivered'}">
                        ${r.active_deliveries} active
                    </span>
                </div>
                <div class="delivery-details">
                    📞 ${r.phone} · ID: ${r.id}
                </div>
            </div>
        `).join('');
    }

    function updateStats(stats) {
        document.getElementById('statTotal').textContent = stats.total_deliveries;
        document.getElementById('statRequested').textContent = stats.by_status.Requested || 0;
        document.getElementById('statAssigned').textContent = stats.by_status.Assigned || 0;
        document.getElementById('statDelivered').textContent = stats.by_status.Delivered || 0;
    }

    function populateRiderSelect(riders) {
        const select = document.getElementById('riderSelect');
        const current = select.value;
        select.innerHTML = '<option value="">-- Select Rider --</option>' +
            Object.values(riders).map(r => `<option value="${r.id}">${r.name}</option>`).join('');
        if (current) select.value = current;
    }

    async function loadRiderDeliveries() {
        const riderId = document.getElementById('riderSelect').value;
        const container = document.getElementById('riderDeliveries');

        if (!riderId) {
            container.innerHTML = `<div class="empty-state"><i class="fas fa-motorcycle"></i><p>Select your rider ID to see assigned deliveries.</p></div>`;
            return;
        }

        const res = await fetch('/api/deliveries');
        const deliveries = await res.json();
        const mine = Object.values(deliveries).filter(d => d.assigned_rider === riderId);

        if (!mine.length) {
            container.innerHTML = `<div class="empty-state"><i class="fas fa-check-circle"></i><p>No deliveries assigned to you right now.</p></div>`;
            return;
        }

        container.innerHTML = mine.map(d => `
            <div class="delivery-item">
                <div class="delivery-header">
                    <span class="delivery-id">${d.id}</span>
                    ${statusBadge(d.status)}
                </div>
                <div class="delivery-details">
                    <strong>${d.customer_name}</strong> · ${d.customer_phone}<br>
                    📍 ${d.delivery_address}<br>
                    📦 ${d.item_description}
                </div>
                <div class="delivery-actions">
                    ${d.status === 'Assigned' ? `
                        <button class="btn btn-small btn-gold" onclick="updateRiderStatus('${d.id}', 'Picked Up')">
                            <i class="fas fa-box"></i> Mark Picked Up
                        </button>
                    ` : ''}
                    ${d.status === 'Picked Up' ? `
                        <button class="btn btn-small" onclick="updateRiderStatus('${d.id}', 'Delivered')">
                            <i class="fas fa-check"></i> Mark Delivered
                        </button>
                    ` : ''}
                    ${d.status === 'Delivered' ? `
                        <span style="color:#155724;font-weight:600;"><i class="fas fa-check-circle"></i> Completed</span>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }

    // ---------- PAUSE POLLING WHILE USER INTERACTS WITH A DROPDOWN ----------
    document.addEventListener('focusin', (e) => {
        if (e.target.tagName === 'SELECT') pollingPaused = true;
    });
    document.addEventListener('focusout', (e) => {
        if (e.target.tagName === 'SELECT') {
            setTimeout(() => { pollingPaused = false; }, 800);
        }
    });

    // ---------- INITIAL LOAD + SSE + POLLING FALLBACK ----------
    loadAll();

    if (typeof(EventSource) !== 'undefined') {
        const es = new EventSource('/api/stream');
        es.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.action === 'refresh') {
                console.log('📡 Real-time update received!');
                loadAll();
            }
        };
        es.onerror = function() { console.log('🔄 SSE reconnecting...'); };
    }

    // Poll only when the user is NOT interacting with a dropdown
    setInterval(() => {
        if (!pollingPaused) loadAll();
    }, 3000);
</script>

</body>
</html>
"""


# ---------- START THE APP ----------
if __name__ == '__main__':
    start_queue_worker()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)