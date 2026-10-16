# Email Processing API Documentation

## Overview

Lightweight REST API for accessing processed email data. Designed for Android app integration with minimal resource usage on AWS t3.micro instances.

**Base URL**: `http://your-aws-ip:5000/api`

## Endpoints

### 1. Health Check

Check API and database health status.

```
GET /api/health
```

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-11-15T10:30:00",
  "database": {
    "total_emails": 145,
    "size_mb": 0.0856
  },
  "last_heartbeat": {
    "id": 1,
    "state": "successfully updated without errors",
    "timestamp": "2024-11-15T10:15:00"
  }
}
```

---

### 2. Get Emails

Retrieve emails with optional filtering.

```
GET /api/emails
```

**Query Parameters**:
- `limit` (optional): Max emails to return (default: 50, max: 200)
- `since` (optional): ISO timestamp - only return emails processed after this
- `priority` (optional): Filter by priority (HIGH, EXTRA_HIGH, LOW)
- `category` (optional): Filter by category

**Example Requests**:
```bash
# Get last 50 emails
curl http://your-ip:5000/api/emails

# Get 20 most recent emails
curl http://your-ip:5000/api/emails?limit=20

# Get emails since last sync
curl http://your-ip:5000/api/emails?since=2024-11-15T10:00:00

# Get high priority emails
curl http://your-ip:5000/api/emails?priority=HIGH&limit=30
```

**Response**:
```json
{
  "count": 2,
  "emails": [
    {
      "gmail_id": 12347,
      "reason": "SDE internship at Company X with approaching deadline",
      "priority": "EXTRA_HIGH",
      "category": "internship",
      "deadline": "2024-11-20T18:00:00",
      "sender": "placements@university.edu",
      "raw_subject": "Internship Opportunity - Company X",
      "raw_body": "Applications are now open...",
      "processed_at": "2024-11-15T10:15:00",
      "model": "qwen3.5:0.8b",
      "created_at": "2024-11-15T10:15:02"
    },
    {
      "gmail_id": 12346,
      "reason": "Assignment submission due next week",
      "priority": "HIGH",
      "category": "assignment",
      "deadline": "2024-11-22T23:59:00",
      "sender": "professor@university.edu",
      "raw_subject": "CS101 Assignment 3",
      "raw_body": "Please submit your assignment...",
      "processed_at": "2024-11-15T10:15:00",
      "model": "qwen3.5:0.8b",
      "created_at": "2024-11-15T10:15:01"
    }
  ],
  "timestamp": "2024-11-15T10:30:00"
}
```

---

### 3. Sync Emails (Recommended for Android)

Optimized endpoint for incremental sync - only returns new emails since last sync.

```
GET /api/emails/sync
```

**Query Parameters**:
- `last_sync` (required): ISO timestamp of last successful sync
- `limit` (optional): Max emails to return (default: 100, max: 200)

**Example Request**:
```bash
curl "http://your-ip:5000/api/emails/sync?last_sync=2024-11-15T10:00:00"
```

**Response**:
```json
{
  "count": 3,
  "new_emails": [
    {
      "gmail_id": 12348,
      "reason": "Placement drive for TCS",
      "priority": "HIGH",
      "category": "placement",
      "deadline": "2024-11-25T12:00:00",
      "sender": "placements@university.edu",
      "raw_subject": "TCS Campus Drive",
      "raw_body": "Registration open...",
      "processed_at": "2024-11-15T10:15:00",
      "model": "qwen3.5:0.8b",
      "created_at": "2024-11-15T10:15:03"
    }
  ],
  "sync_timestamp": "2024-11-15T10:30:00",
  "has_more": false
}
```

**Android Usage**:
```kotlin
// Save this timestamp after successful sync
val lastSync = "2024-11-15T10:30:00"
sharedPreferences.edit()
    .putString("last_sync", lastSync)
    .apply()

// Next sync - only fetch new emails
val nextSync = apiService.syncEmails(lastSync)
```

---

### 4. Get Emails by Priority

Filter emails by priority level.

```
GET /api/emails/priority/{priority}
```

**Path Parameters**:
- `priority`: HIGH, EXTRA_HIGH, or LOW

**Query Parameters**:
- `limit` (optional): Max emails (default: 50, max: 200)

**Example Request**:
```bash
curl http://your-ip:5000/api/emails/priority/EXTRA_HIGH
```

**Response**:
```json
{
  "priority": "EXTRA_HIGH",
  "count": 1,
  "emails": [...],
  "timestamp": "2024-11-15T10:30:00"
}
```

---

### 5. Get Emails by Category

Filter emails by category.

```
GET /api/emails/category/{category}
```

**Path Parameters**:
- `category`: internship, placement, hackathon, assignment, exam, fee_payment, registration, security_alert, event, other

**Query Parameters**:
- `limit` (optional): Max emails (default: 50, max: 200)

**Example Request**:
```bash
curl http://your-ip:5000/api/emails/category/internship?limit=10
```

**Response**:
```json
{
  "category": "internship",
  "count": 5,
  "emails": [...],
  "timestamp": "2024-11-15T10:30:00"
}
```

---

### 6. Get Statistics

Get database statistics and breakdowns.

```
GET /api/stats
```

**Example Request**:
```bash
curl http://your-ip:5000/api/stats
```

**Response**:
```json
{
  "total_emails": 145,
  "priority_breakdown": {
    "HIGH": 45,
    "EXTRA_HIGH": 12,
    "LOW": 88
  },
  "category_breakdown": {
    "internship": 15,
    "placement": 10,
    "assignment": 25,
    "exam": 8,
    "event": 45,
    "other": 42
  },
  "database_size_mb": 0.0856,
  "timestamp": "2024-11-15T10:30:00"
}
```

---

### 7. Get Heartbeat

Get recent system heartbeat entries for monitoring.

```
GET /api/heartbeat
```

**Query Parameters**:
- `limit` (optional): Number of entries (default: 10, max: 50)

**Example Request**:
```bash
curl http://your-ip:5000/api/heartbeat?limit=5
```

**Response**:
```json
{
  "count": 5,
  "heartbeats": [
    {
      "id": 5,
      "state": "successfully updated without errors",
      "timestamp": "2024-11-15T10:15:00",
      "created_at": "2024-11-15T10:15:01"
    },
    {
      "id": 4,
      "state": "processing_emails",
      "timestamp": "2024-11-15T10:14:30",
      "created_at": "2024-11-15T10:14:31"
    }
  ],
  "timestamp": "2024-11-15T10:30:00"
}
```

---

## Android Integration Example

### Retrofit Interface

```kotlin
interface EmailApiService {
    @GET("api/emails/sync")
    suspend fun syncEmails(
        @Query("last_sync") lastSync: String,
        @Query("limit") limit: Int = 100
    ): SyncResponse

    @GET("api/emails/priority/{priority}")
    suspend fun getEmailsByPriority(
        @Path("priority") priority: String,
        @Query("limit") limit: Int = 50
    ): EmailsResponse

    @GET("api/stats")
    suspend fun getStats(): StatsResponse

    @GET("api/health")
    suspend fun healthCheck(): HealthResponse
}
```

### Data Classes

```kotlin
data class SyncResponse(
    val count: Int,
    val new_emails: List<Email>,
    val sync_timestamp: String,
    val has_more: Boolean
)

data class Email(
    val gmail_id: Long,
    val reason: String,
    val priority: String,
    val category: String,
    val deadline: String?,
    val sender: String,
    val raw_subject: String,
    val raw_body: String,
    val processed_at: String,
    val model: String
)

data class StatsResponse(
    val total_emails: Int,
    val priority_breakdown: Map<String, Int>,
    val category_breakdown: Map<String, Int>,
    val database_size_mb: Double,
    val timestamp: String
)
```

### WorkManager Setup

```kotlin
class EmailSyncWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        return try {
            val sharedPrefs = applicationContext.getSharedPreferences("email_sync", Context.MODE_PRIVATE)
            val lastSync = sharedPrefs.getString("last_sync", "2024-01-01T00:00:00") ?: "2024-01-01T00:00:00"

            val response = apiService.syncEmails(lastSync)

            // Save to local Room database
            emailDao.insertAll(response.new_emails)

            // Update last sync timestamp
            sharedPrefs.edit()
                .putString("last_sync", response.sync_timestamp)
                .apply()

            // Show notification for EXTRA_HIGH priority
            response.new_emails
                .filter { it.priority == "EXTRA_HIGH" }
                .forEach { showNotification(it) }

            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }
}

// Schedule periodic sync (every 15 minutes, only on WiFi)
val constraints = Constraints.Builder()
    .setRequiredNetworkType(NetworkType.UNMETERED)
    .build()

val syncRequest = PeriodicWorkRequestBuilder<EmailSyncWorker>(15, TimeUnit.MINUTES)
    .setConstraints(constraints)
    .build()

WorkManager.getInstance(context).enqueueUniquePeriodicWork(
    "email_sync",
    ExistingPeriodicWorkPolicy.KEEP,
    syncRequest
)
```

---

## Error Responses

All endpoints return consistent error responses:

```json
{
  "error": "Error message description",
  "timestamp": "2024-11-15T10:30:00"
}
```

**Common HTTP Status Codes**:
- `200 OK` - Success
- `400 Bad Request` - Invalid parameters
- `404 Not Found` - Endpoint not found
- `500 Internal Server Error` - Server error

---

## Performance Considerations

- **Response time**: Typical < 50ms on t3.micro
- **Max limit**: 200 emails per request (prevents memory issues)
- **Recommended sync interval**: 15 minutes
- **Use `/api/emails/sync`**: More efficient than fetching all emails
- **Database size**: ~60KB per 100 emails

---

## Production Deployment

The API runs with Gunicorn (2 workers) for better performance:

```bash
gunicorn -w 2 -b 0.0.0.0:5000 api:app
```

Managed by systemd for automatic restart and monitoring.

---

## Security Notes

Since this is a personal project:
- No authentication required (hardcoded values in Android app)
- API accessible only from your AWS instance IP
- Use AWS Security Groups to restrict access to your IP only
- Consider adding HTTPS with Let's Encrypt for production use

To add IP restriction in AWS Security Group:
1. EC2 Console → Security Groups
2. Edit Inbound Rules
3. Add rule: Custom TCP, Port 5000, Source: Your Android IP/32

---

## Monitoring

Check service status:
```bash
# API service
sudo systemctl status email-api

# Email processor timer
sudo systemctl status email-processor.timer

# View logs
sudo tail -f /var/log/email-api.log
sudo tail -f /var/log/email-processor.log
```

Test API locally:
```bash
# Health check
curl http://localhost:5000/api/health

# Get emails
curl http://localhost:5000/api/emails?limit=5
```
