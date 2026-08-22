# app.py - Solstice Events Kiosk Service (Async + Webhooks)
from flask import Flask, request, jsonify, render_template_string, Response, stream_with_context
import datetime
import json
import uuid
import time
import threading
from collections import defaultdict

app = Flask(__name__)

# ---------- In-Memory "Database" ----------
# In production, this would be Redis or a real database.
# For this simulation, we use Python dictionaries.

# Attendee database
attendees = {
    "ATT-001": {"name": "Alice Johnson", "email": "alice@example.com", "checked_in": False, "pending": False},
    "ATT-002": {"name": "Bob Smith", "email": "bob@example.com", "checked_in": False, "pending": False},
    "ATT-003": {"name": "Carol White", "email": "carol@example.com", "checked_in": False, "pending": False},
    "ATT-004": {"name": "David Brown", "email": "david@example.com", "checked_in": False, "pending": False},
}

# Print jobs queue (simulated message queue)
print_queue = []

# Completed print jobs (for webhook callbacks)
completed_jobs = []

# Duplicate scan protection
scanned_tickets = set()

# Webhook endpoint for the vendor to call back
VENDOR_WEBHOOK_URL = "http://127.0.0.1:5001/webhook/print-complete"


# ---------- SIMULATED MESSAGE QUEUE ----------
def process_print_queue():
    """
    Simulates a worker that processes the message queue.
    In production, this would be a separate service (Celery, Redis, etc.)
    """
    while True:
        if print_queue:
            job = print_queue.pop(0)
            print(f"🖨️ Processing print job: {job['ticket_id']} for {job['attendee_name']}")
            
            # Simulate print time (2-5 seconds)
            time.sleep(3)
            
            # Complete the job
            completed_jobs.append({
                "ticket_id": job["ticket_id"],
                "attendee_id": job["attendee_id"],
                "status": "completed",
                "timestamp": str(datetime.datetime.now())
            })
            
            # Send webhook callback (simulate vendor calling back)
            send_webhook_callback(job["attendee_id"], job["ticket_id"])
        else:
            time.sleep(1)


def send_webhook_callback(attendee_id, ticket_id):
    """
    Simulates the vendor calling our webhook endpoint.
    In production, the vendor would call our exposed webhook URL.
    """
    # Simulate network delay (1-3 seconds)
    time.sleep(2)
    
    # Call our own webhook endpoint (simulating vendor callback)
    with app.test_client() as client:
        response = client.post('/webhook/print-complete', 
                               json={
                                   "attendee_id": attendee_id,
                                   "ticket_id": ticket_id,
                                   "status": "success",
                                   "timestamp": str(datetime.datetime.now())
                               })
        print(f"📡 Webhook callback sent for {attendee_id}: {response.status_code}")


# ---------- FLASK ROUTES ----------

@app.route('/')
def index():
    """Serve the kiosk UI"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/attendees', methods=['GET'])
def get_attendees():
    """Return list of all attendees (for UI)"""
    return jsonify(attendees)


@app.route('/api/scan', methods=['POST'])
def scan_ticket():
    """
    Scan QR code (simulated).
    Instead of calling the printer sync, we publish to a queue.
    """
    data = request.get_json()
    attendee_id = data.get('attendee_id', '').strip()
    
    # Validate input
    if not attendee_id:
        return jsonify({"error": "No attendee ID provided"}), 400
    
    # Check if attendee exists
    if attendee_id not in attendees:
        return jsonify({"error": "Attendee not found"}), 404
    
    attendee = attendees[attendee_id]
    
    # DUPLICATE SCAN PROTECTION (even with async callbacks)
    if attendee_id in scanned_tickets:
        return jsonify({
            "error": "Already scanned",
            "message": f"{attendee['name']} has already been checked in.",
            "attendee_id": attendee_id,
            "status": "duplicate"
        }), 409
    
    # Check if already checked in (from a previous callback)
    if attendee['checked_in']:
        return jsonify({
            "error": "Already checked in",
            "message": f"{attendee['name']} is already checked in.",
            "attendee_id": attendee_id,
            "status": "already_checked_in"
        }), 409
    
    # Mark as pending (waiting for print confirmation)
    attendees[attendee_id]['pending'] = True
    scanned_tickets.add(attendee_id)
    
    # Generate a unique ticket ID for this print job
    ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
    
    # PUBLISH TO MESSAGE QUEUE (instead of sync API call)
    print_queue.append({
        "ticket_id": ticket_id,
        "attendee_id": attendee_id,
        "attendee_name": attendee['name'],
        "timestamp": str(datetime.datetime.now())
    })
    
    return jsonify({
        "status": "pending",
        "message": f"Print request submitted for {attendee['name']}. Waiting for confirmation...",
        "attendee_id": attendee_id,
        "ticket_id": ticket_id,
        "queue_position": len(print_queue)
    }), 202  # 202 Accepted (async processing)


@app.route('/webhook/print-complete', methods=['POST'])
def print_complete_webhook():
    """
    Webhook endpoint for the vendor to call back when print is complete.
    This is the key pivot: we receive a callback instead of waiting synchronously.
    """
    data = request.get_json()
    print(f"📩 Webhook received: {data}")
    
    attendee_id = data.get('attendee_id')
    ticket_id = data.get('ticket_id')
    status = data.get('status', 'success')
    
    if not attendee_id or attendee_id not in attendees:
        return jsonify({"error": "Invalid attendee ID"}), 400
    
    attendee = attendees[attendee_id]
    
    # Check if attendee is already checked in (prevents double processing)
    if attendee['checked_in']:
        return jsonify({"message": "Already checked in, ignoring duplicate webhook"}), 200
    
    # Update the attendee status
    if status == 'success':
        attendee['checked_in'] = True
        attendee['pending'] = False
        attendee['checked_in_at'] = data.get('timestamp', str(datetime.datetime.now()))
        attendee['ticket_id'] = ticket_id
        
        print(f"✅ {attendee['name']} (ID: {attendee_id}) checked in successfully!")
    else:
        # If print failed, we need to handle it gracefully
        attendee['pending'] = False
        attendee['print_failed'] = True
        print(f"❌ Print failed for {attendee['name']} (ID: {attendee_id})")
    
    return jsonify({"status": "success", "message": "Webhook processed"}), 200


@app.route('/api/attendee/<attendee_id>', methods=['GET'])
def get_attendee_status(attendee_id):
    """Get status of a specific attendee (for UI polling)"""
    if attendee_id not in attendees:
        return jsonify({"error": "Attendee not found"}), 404
    
    attendee = attendees[attendee_id]
    return jsonify({
        "attendee_id": attendee_id,
        "name": attendee['name'],
        "email": attendee['email'],
        "checked_in": attendee['checked_in'],
        "pending": attendee.get('pending', False),
        "checked_in_at": attendee.get('checked_in_at', None)
    })


@app.route('/api/queue', methods=['GET'])
def get_queue_status():
    """Get the current queue status (for monitoring)"""
    return jsonify({
        "queue_length": len(print_queue),
        "pending_jobs": print_queue,
        "completed_jobs": completed_jobs[-10:]  # Last 10 completed jobs
    })


# ---------- SERVER-SENT EVENTS (REAL-TIME UPDATES) ----------
@app.route('/api/stream')
def event_stream():
    """Server-Sent Events endpoint for real-time updates."""
    def generate():
        last_checked_in_count = 0
        last_queue_length = 0
        while True:
            time.sleep(1)
            
            # Check if anything changed
            current_checked_in = sum(1 for a in attendees.values() if a['checked_in'])
            current_queue_length = len(print_queue)
            
            if current_checked_in != last_checked_in_count or current_queue_length != last_queue_length:
                last_checked_in_count = current_checked_in
                last_queue_length = current_queue_length
                yield f"data: {json.dumps({'action': 'refresh'})}\n\n"
    
    return Response(generate(), mimetype="text/event-stream")


# ---------- START THE QUEUE WORKER ----------
def start_queue_worker():
    """Start the background queue processing thread"""
    worker_thread = threading.Thread(target=process_print_queue, daemon=True)
    worker_thread.start()
    print("🚀 Queue worker started!")


# ---------- START THE QUEUE WORKER ----------
def start_queue_worker():
    """Start the background queue processing thread"""
    worker_thread = threading.Thread(target=process_print_queue, daemon=True)
    worker_thread.start()
    print("🚀 Queue worker started!")


# ---------- HTML TEMPLATE (Kiosk UI) ----------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Solstice Events · Check-In Kiosk</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" />
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a1628;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            max-width: 700px;
            width: 100%;
            background: #ffffff;
            border-radius: 24px;
            padding: 40px 32px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #0a1628;
            font-size: 2rem;
        }
        .header h1 i {
            color: #d4af37;
            margin-right: 10px;
        }
        .header p {
            color: #6b7f94;
            font-size: 1rem;
        }
        .header .badge-status {
            display: inline-block;
            background: #d4af37;
            color: #0a1628;
            padding: 4px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.8rem;
            margin-top: 8px;
        }
        .scan-section {
            background: #f8fafd;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            border: 2px dashed #d4af37;
        }
        .scan-section label {
            display: block;
            font-weight: 600;
            color: #0a1628;
            margin-bottom: 8px;
        }
        .scan-section .input-group {
            display: flex;
            gap: 10px;
        }
        .scan-section input {
            flex: 1;
            padding: 14px 18px;
            border: 2px solid #e2e8f0;
            border-radius: 12px;
            font-size: 1rem;
            font-family: monospace;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        .scan-section input:focus {
            border-color: #d4af37;
            outline: none;
        }
        .scan-section button {
            background: #0a1628;
            color: white;
            border: none;
            padding: 14px 28px;
            border-radius: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
        }
        .scan-section button:hover {
            background: #1a2b4c;
            transform: scale(1.02);
        }
        .scan-section button:active {
            transform: scale(0.97);
        }
        .result-box {
            background: #f0f4fe;
            border-radius: 12px;
            padding: 16px 20px;
            margin-top: 15px;
            border-left: 4px solid #d4af37;
            min-height: 60px;
        }
        .result-box .success {
            color: #1a7d4a;
        }
        .result-box .pending {
            color: #a66b1e;
        }
        .result-box .error {
            color: #c0392b;
        }
        .result-box .duplicate {
            color: #8a6d3b;
        }
        .attendee-list {
            margin-top: 20px;
        }
        .attendee-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: #f8fafd;
            border-radius: 10px;
            margin-bottom: 8px;
            border: 1px solid #e2e8f0;
        }
        .attendee-item .name {
            font-weight: 600;
            color: #0a1628;
        }
        .attendee-item .id {
            color: #6b7f94;
            font-size: 0.85rem;
            font-family: monospace;
        }
        .attendee-item .status-badge {
            font-size: 0.75rem;
            font-weight: 600;
            padding: 4px 12px;
            border-radius: 20px;
        }
        .status-badge.checked-in {
            background: #d4edda;
            color: #155724;
        }
        .status-badge.pending {
            background: #fff3cd;
            color: #856404;
        }
        .status-badge.not-checked {
            background: #e2e8f0;
            color: #6b7f94;
        }
        .status-badge.duplicate {
            background: #f8d7da;
            color: #721c24;
        }
        .status-badge.print-failed {
            background: #f8d7da;
            color: #721c24;
        }
        .status-icon {
            margin-right: 6px;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            font-size: 0.8rem;
            color: #8a9baa;
        }
        .queue-status {
            background: #f0f4fe;
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 0.8rem;
            color: #0a1628;
            margin-top: 10px;
            display: flex;
            justify-content: space-between;
        }
        .spinner {
            display: inline-block;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .pulsing {
            animation: pulse 1.5s ease-in-out infinite;
        }
        .demo-hint {
            background: #e8f0fe;
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 0.85rem;
            color: #0a1628;
            margin-bottom: 15px;
            border: 1px solid #d4af37;
        }
        .demo-hint code {
            background: #0a1628;
            color: #d4af37;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
        }
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <h1><i class="fas fa-ticket-alt"></i> Solstice Events</h1>
        <p>Conference Check-In Kiosk</p>
        <span class="badge-status"><i class="fas fa-robot"></i> Async Print System</span>
    </div>

    <div class="demo-hint">
        <i class="fas fa-info-circle"></i>
        Test IDs: <code>ATT-001</code> (Alice), <code>ATT-002</code> (Bob), <code>ATT-003</code> (Carol)
        <br><small>Scan the same ID twice to test duplicate protection!</small>
    </div>

    <!-- SCAN SECTION -->
    <div class="scan-section">
        <label><i class="fas fa-qrcode"></i> Scan Attendee QR Code</label>
        <div class="input-group">
            <input type="text" id="attendeeId" placeholder="e.g. ATT-001" />
            <button onclick="scanAttendee()">
                <i class="fas fa-camera"></i> Scan
            </button>
        </div>
        <div id="result" class="result-box">
            <i class="fas fa-info-circle text-muted"></i>
            <span class="text-muted">Ready to scan...</span>
        </div>
    </div>

    <!-- QUEUE STATUS -->
    <div class="queue-status">
        <span><i class="fas fa-queue"></i> Queue: <span id="queueCount">0</span> jobs</span>
        <span><i class="fas fa-check-circle" style="color:#1a7d4a;"></i> Completed: <span id="completedCount">0</span></span>
        <span><i class="fas fa-users"></i> Checked In: <span id="checkedInCount">0</span></span>
    </div>

    <!-- ATTENDEE LIST -->
    <div class="attendee-list" id="attendeeList">
        <h3 style="margin-bottom:10px;color:#0a1628;font-size:0.9rem;">
            <i class="fas fa-users"></i> Attendees
        </h3>
        <div id="attendeesContainer">
            <!-- Dynamically loaded -->
        </div>
    </div>

    <div class="footer">
        <i class="fas fa-robot"></i> Async Event-Driven Architecture · Webhook Callbacks
    </div>
</div>

<script>
    // ---------- SCAN ATTENDEE ----------
    async function scanAttendee() {
        const input = document.getElementById('attendeeId');
        const result = document.getElementById('result');
        const attendeeId = input.value.trim();

        if (!attendeeId) {
            result.innerHTML = `
                <i class="fas fa-exclamation-triangle" style="color:#d4af37;"></i>
                Please enter an Attendee ID.
            `;
            return;
        }

        // Show pending/loading state
        result.innerHTML = `
            <div style="display:flex;align-items:center;gap:12px;">
                <i class="fas fa-spinner fa-pulse" style="color:#d4af37;font-size:1.2rem;"></i>
                <span>Scanning <strong>${attendeeId}</strong>... Submitting print request.</span>
            </div>
        `;

        try {
            const response = await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ attendee_id: attendeeId })
            });

            const data = await response.json();

            if (response.status === 202) {
                // Accepted (pending)
                result.innerHTML = `
                    <div class="pending" style="display:flex;align-items:center;gap:12px;">
                        <i class="fas fa-clock fa-pulse"></i>
                        <div>
                            <strong>${data.message}</strong>
                            <br><small style="color:#6b7f94;">
                                Ticket ID: ${data.ticket_id} · Queue position: ${data.queue_position}
                            </small>
                        </div>
                    </div>
                `;
            } else if (response.status === 409) {
                // Duplicate or already checked in
                const isDuplicate = data.status === 'duplicate';
                const icon = isDuplicate ? 'fa-ban' : 'fa-check-circle';
                const cls = isDuplicate ? 'duplicate' : 'success';
                result.innerHTML = `
                    <div class="${cls}" style="display:flex;align-items:center;gap:12px;">
                        <i class="fas ${icon}"></i>
                        <div>
                            <strong>${data.message}</strong>
                            <br><small style="color:#6b7f94;">Status: ${data.status}</small>
                        </div>
                    </div>
                `;
            } else if (response.status === 404) {
                result.innerHTML = `
                    <div class="error" style="display:flex;align-items:center;gap:12px;">
                        <i class="fas fa-user-slash"></i>
                        <div>
                            <strong>Attendee not found.</strong>
                            <br><small style="color:#6b7f94;">Please check the ID and try again.</small>
                        </div>
                    </div>
                `;
            } else {
                result.innerHTML = `
                    <div class="error" style="display:flex;align-items:center;gap:12px;">
                        <i class="fas fa-exclamation-circle"></i>
                        <div>
                            <strong>Error: ${data.error || 'Unknown error'}</strong>
                        </div>
                    </div>
                `;
            }
        } catch (error) {
            result.innerHTML = `
                <div class="error" style="display:flex;align-items:center;gap:12px;">
                    <i class="fas fa-server"></i>
                    <div>
                        <strong>Network error. Please try again.</strong>
                        <br><small style="color:#6b7f94;">${error.message}</small>
                    </div>
                </div>
            `;
        }

        // Clear input and refresh attendees
        input.value = '';
        setTimeout(loadAttendees, 500);
    }

    // ---------- LOAD ATTENDEES ----------
    async function loadAttendees() {
        try {
            const response = await fetch('/api/attendees');
            const data = await response.json();

            const container = document.getElementById('attendeesContainer');
            let html = '';
            let checkedInCount = 0;

            for (const [id, attendee] of Object.entries(data)) {
                let statusClass = 'not-checked';
                let statusText = 'Not Checked';
                let icon = 'fa-user';

                if (attendee.checked_in) {
                    statusClass = 'checked-in';
                    statusText = '✅ Checked In';
                    icon = 'fa-check-circle';
                    checkedInCount++;
                } else if (attendee.pending) {
                    statusClass = 'pending';
                    statusText = '⏳ Pending...';
                    icon = 'fa-clock';
                } else if (attendee.print_failed) {
                    statusClass = 'print-failed';
                    statusText = '❌ Print Failed';
                    icon = 'fa-exclamation-triangle';
                }

                html += `
                    <div class="attendee-item">
                        <div>
                            <span class="name">${attendee.name}</span>
                            <span class="id">(${id})</span>
                        </div>
                        <div>
                            <span class="status-badge ${statusClass}">
                                <i class="fas ${icon}"></i> ${statusText}
                            </span>
                        </div>
                    </div>
                `;
            }

            container.innerHTML = html;
            document.getElementById('checkedInCount').textContent = checkedInCount;

        } catch (error) {
            console.error('Failed to load attendees:', error);
        }
    }

    // ---------- LOAD QUEUE STATUS ----------
    async function loadQueueStatus() {
        try {
            const response = await fetch('/api/queue');
            const data = await response.json();
            document.getElementById('queueCount').textContent = data.queue_length;
            document.getElementById('completedCount').textContent = data.completed_jobs.length;
        } catch (error) {
            console.error('Failed to load queue:', error);
        }
    }

    // ---------- ENTER KEY SUPPORT ----------
    document.getElementById('attendeeId').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            scanAttendee();
        }
    });

       // ---------- REAL-TIME UPDATES WITH SSE ----------
    // Use Server-Sent Events for instant updates instead of polling
    loadAttendees();
    loadQueueStatus();

    // Check if browser supports EventSource
    if (typeof(EventSource) !== 'undefined') {
        const eventSource = new EventSource('/api/stream');
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.action === 'refresh') {
                console.log('📡 Real-time update received!');
                loadAttendees();
                loadQueueStatus();
            }
        };

        eventSource.onerror = function() {
            console.log('🔄 SSE connection lost. Reconnecting...');
            // Browser automatically reconnects after a delay
        };
    } else {
        // Fallback for older browsers: poll every 5 seconds
        console.log('⚠️ EventSource not supported. Using polling fallback.');
        setInterval(() => {
            loadAttendees();
            loadQueueStatus();
        }, 5000);
    }

    // Also auto-refresh when a scan happens (already called in scanAttendee)
</script>

</body>
</html>
"""


# ---------- START THE APP ----------
if __name__ == '__main__':
    # Start the queue worker thread
    start_queue_worker()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5001, debug=True)

    