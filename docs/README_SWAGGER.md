# Swagger Documentation - Quick Reference

## 🚀 Updated Swagger Documentation

The NVIDIA Orchestrator API Swagger documentation has been successfully updated and is now available in multiple formats.

---

## 📖 Access Points

### Interactive Documentation
- **🌐 Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **📋 ReDoc Interface**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Raw Specifications
- **📄 OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
- **📁 Local Files**:
  - `openapi-spec-updated.json` - Latest OpenAPI specification
  - `openapi-spec-updated-formatted.json` - Pretty-formatted version

---

## 📚 Documentation Files

### Comprehensive Guide
- **📖 API_DOCUMENTATION.md** - Complete endpoint documentation with examples
- **🔧 postman-collection.json** - Ready-to-import Postman collection

### Testing Tools
- **Postman Collection**: Import `postman-collection.json` into Postman
- **cURL Examples**: Available in the comprehensive documentation
- **Interactive Testing**: Use Swagger UI for immediate testing

---

## 🎯 Key Features

### ✅ What's Included
- **16 API Endpoints** across 3 main categories
- **Interactive Testing** via Swagger UI
- **Complete Request/Response Examples**
- **Data Model Specifications**
- **Error Response Documentation**
- **Authentication & CORS Information**

### 📋 Endpoint Categories
1. **Health & Monitoring** (4 endpoints)
   - Basic health check
   - Detailed system health
   - Integration testing
   - System resource monitoring

2. **Container Management** (9 endpoints)
   - Container lifecycle management
   - Resource allocation
   - Health monitoring
   - Image instance management

3. **Service Registry** (3 endpoints)
   - Endpoint registration
   - Status management
   - Service discovery

---

## 🔧 Quick Start

### 1. View Interactive Documentation
```bash
# Open Swagger UI in browser
start http://localhost:8000/docs
```

### 2. Import Postman Collection
1. Open Postman
2. Import → Upload Files
3. Select `postman-collection.json`
4. Start testing endpoints

### 3. Test with cURL
```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health/detailed

# List containers
curl http://localhost:8000/containers
```

---

## 🚦 Current Status

**API Server**: ✅ Running (Docker containerized)  
**Database**: ✅ PostgreSQL connected  
**Health Monitor**: ✅ Active monitoring  
**Documentation**: ✅ Updated and verified  

---

## 📊 System Overview

```
🐳 Docker Services:
├── orchestrator-api-dev        (Port 8000)
├── orchestrator-monitor-dev    (Health monitoring)
└── orchestrator-postgres-dev   (Port 5432)

📖 Documentation Access:
├── http://localhost:8000/docs     (Swagger UI)
├── http://localhost:8000/redoc    (ReDoc)
└── API_DOCUMENTATION.md           (Comprehensive guide)
```

---

## 🔍 Verification

All documentation has been verified against the running API:
- ✅ OpenAPI specification generated from live API
- ✅ All endpoints tested and responding
- ✅ Docker services healthy and operational
- ✅ Interactive Swagger UI functional

---

*Last Updated: $(date)*  
*API Version: 1.0.0*  
*Documentation Status: ✅ Current* 