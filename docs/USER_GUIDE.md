# PROVENIQ Ops — User Guide

**Version:** 1.0.0  
**Last Updated:** December 2024

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Dashboard Overview](#3-dashboard-overview)
4. [Scanning Inventory](#4-scanning-inventory)
5. [Managing Inventory](#5-managing-inventory)
6. [Par Levels & Reordering](#6-par-levels--reordering)
7. [Vendor Management](#7-vendor-management)
8. [Team Management](#8-team-management)
9. [Shrinkage Detection](#9-shrinkage-detection)
10. [Reports & Analytics](#10-reports--analytics)
11. [Settings](#11-settings)
12. [Troubleshooting](#12-troubleshooting)
13. [Support](#13-support)

---

## 1. Introduction

### What is PROVENIQ Ops?

PROVENIQ Ops is a mobile-first inventory management system designed for:

- **Restaurants & Food Service** — Kitchens, cafeterias, bars, catering
- **Retail Stores** — Shops, boutiques, convenience stores
- **Warehouses** — Storage facilities, distribution centers

### Key Features

| Feature | Description |
|---------|-------------|
| **Barcode Scanning** | Scan items with your phone camera |
| **Shrinkage Detection** | Identify theft, spoilage, and variance |
| **Auto-Ordering** | Automatic reorder when stock is low |
| **Vendor Integration** | Connect to SYSCO, US Foods, and more |
| **Team Management** | Invite staff with role-based permissions |
| **Real-Time Visibility** | See inventory across all locations |

### System Requirements

- **iOS:** Version 14.0 or later
- **Android:** Version 10.0 or later
- **Internet:** Required for sync and ordering

---

## 2. Getting Started

### Download the App

1. Open the **App Store** (iOS) or **Google Play Store** (Android)
2. Search for "PROVENIQ Ops"
3. Tap **Install**

### Create Your Account

1. Open the app and tap **Get Started**
2. Enter your email and create a password
3. Verify your email address

### Complete Onboarding

The setup wizard guides you through:

| Step | What You'll Do |
|------|----------------|
| 1. Welcome | Learn about PROVENIQ Ops features |
| 2. Business Info | Enter your business name and contact |
| 3. Business Type | Select Restaurant, Retail, or Warehouse |
| 4. First Location | Create your first location |
| 5. Vendors | Connect your food/product distributors |
| 6. Team | Invite team members (optional) |
| 7. Tutorial | Quick walkthrough of scanning |

**Time to complete:** ~3 minutes

---

## 3. Dashboard Overview

After onboarding, you'll see the main dashboard:

### Header
- **Greeting** — "Good morning, [Name]"
- **Current Location** — 📍 Shows active location
- **Settings** — ⚙️ Access app settings

### Status Card
Shows the current system state:
- **IDLE** — Ready to scan
- **SCANNING** — Scan in progress
- **ANALYZING_RISK** — Checking for issues
- **CHECKING_FUNDS** — Verifying budget
- **ORDER_QUEUED** — Order submitted

### Quick Actions

| Action | Description |
|--------|-------------|
| 📷 **Scan Inventory** | Start a new inventory scan |
| 📦 **View Inventory** | See all items and stock levels |
| 🛒 **Orders** | View pending and past orders |
| ⚠️ **Alerts** | Items below par level |

### Today's Overview
- **Items Scanned** — Total items scanned today
- **Orders Queued** — Orders waiting for approval
- **Below Par** — Items needing reorder

### Bottom Navigation
- **Home** — Dashboard
- **Scan** — Quick access to scanner
- **Inventory** — Full inventory list
- **Orders** — Order management

---

## 4. Scanning Inventory

### Starting a Scan

1. Tap **Scan Inventory** or the **Scan** tab
2. Grant camera permission if prompted
3. Tap **BEGIN SCAN**

### Scanning Items

1. Point camera at barcode (6-12 inches away)
2. Hold steady until detected (you'll see a highlight)
3. Item appears in the detected list
4. Continue scanning more items

### Scan Tips

| Tip | Why |
|-----|-----|
| **Good lighting** | Barcodes need light to be readable |
| **Steady hand** | Movement causes blur |
| **Clean lens** | Smudges reduce accuracy |
| **Correct distance** | Too close/far won't focus |
| **Landscape mode** | Better for long barcodes |

### Completing a Scan

1. Tap **COMPLETE (X)** when finished (X = item count)
2. Review detected items
3. The system checks for discrepancies
4. If items are below par, you'll see reorder suggestions

### Unknown Barcodes

If a barcode isn't recognized:
1. You'll see "Unknown Item" in the list
2. Tap to add item details manually
3. Enter name, category, and par level
4. Save to add to your inventory

---

## 5. Managing Inventory

### Viewing Inventory

1. Tap **Inventory** in bottom nav
2. See all items with current quantities
3. Use search to find specific items
4. Filter by category or status

### Item Details

Tap any item to see:
- **Current Quantity** — Stock on hand
- **Par Level** — Minimum target
- **Last Scanned** — When it was counted
- **Vendor** — Who supplies it
- **Unit Cost** — Price per unit

### Adding Items Manually

1. Tap **+** in inventory screen
2. Enter item details:
   - Name (required)
   - Barcode (optional)
   - Category
   - Par Level
   - Vendor
   - Unit Cost
3. Tap **Save**

### Editing Items

1. Tap item in inventory list
2. Tap **Edit**
3. Update details
4. Tap **Save**

### Deleting Items

1. Tap item in inventory list
2. Tap **Delete**
3. Confirm deletion

> ⚠️ **Warning:** Deleting an item removes all history. Consider setting quantity to 0 instead.

---

## 6. Par Levels & Reordering

### What is a Par Level?

A par level is the **minimum quantity** you want to keep in stock. When inventory falls below par, the system triggers a reorder alert.

**Example:**
- Par Level: 10 gallons of milk
- Current Quantity: 3 gallons
- Result: Alert + Reorder suggestion for 7 gallons

### Setting Par Levels

1. Go to **Inventory**
2. Tap an item
3. Tap **Edit**
4. Set **Par Level**
5. Save

### Reorder Points

You can also set a **Reorder Point** — a threshold that triggers the order before hitting par level.

- **Par Level:** 10 (absolute minimum)
- **Reorder Point:** 15 (trigger order when you hit 15)

### Auto-Ordering

When enabled, the system automatically creates orders when items hit reorder point:

1. Go to **Settings > Ordering**
2. Enable **Auto-Create Orders**
3. Set **Auto-Approve Threshold** (orders under this amount auto-approve)

### Order Approval Workflow

| Your Role | What Happens |
|-----------|--------------|
| **Operator** | Order created, needs Manager approval |
| **Manager** | Can approve orders up to daily limit |
| **Owner** | Can approve any order |

### Viewing Pending Orders

1. Tap **Orders** in bottom nav
2. See **Pending** tab for orders awaiting approval
3. Tap order to review details
4. Approve or Reject

---

## 7. Vendor Management

### Supported Vendors

| Vendor | Type |
|--------|------|
| **SYSCO** | Food service distribution |
| **US Foods** | Food service distribution |
| **Performance Food Group** | Food service distribution |
| **Gordon Food Service** | Regional food service |

### Connecting a Vendor

1. Go to **Settings > Vendors**
2. Tap vendor name
3. Tap **Connect Account**
4. Enter:
   - Customer Number
   - API Key (if available)
   - API Secret (if available)
5. Tap **Connect**

### Getting API Credentials

Contact your vendor sales representative to request API access. Not all accounts have API access by default.

### Using Multiple Vendors

You can connect multiple vendors. When ordering:
- System compares prices across vendors
- Shows availability at each vendor
- Recommends best option
- You choose which vendor to use

### Setting Preferred Vendors

For each item, you can set a preferred vendor:
1. Go to **Inventory** > select item
2. Tap **Edit**
3. Set **Preferred Vendor**
4. Orders will default to this vendor

---

## 8. Team Management

### User Roles

| Role | Permissions |
|------|-------------|
| **Owner** | Full control, billing, delete business, change roles |
| **Manager** | Manage team, approve orders, edit par levels, view all reports |
| **Operator** | Scan inventory, create orders (needs approval), report shrinkage |
| **Viewer** | Read-only access to inventory and reports |

### Inviting Team Members

1. Go to **Settings > Team**
2. Tap **Invite Member**
3. Enter their email
4. Select role (Manager, Operator, or Viewer)
5. Select which locations they can access
6. Tap **Send Invite**

They'll receive an email with instructions to join.

### Managing Team Members

1. Go to **Settings > Team**
2. Tap a team member
3. Options:
   - Change role
   - Change location access
   - Suspend access
   - Remove from team

### Location-Based Access

You can restrict team members to specific locations:
- An Operator at "Downtown Store" only sees that location
- A Manager might have access to all locations
- Useful for multi-location businesses

---

## 9. Shrinkage Detection

### What is Shrinkage?

Shrinkage is inventory loss from:
- **Theft** — Employee or customer theft
- **Spoilage** — Expired or spoiled goods
- **Damage** — Broken or unusable items
- **Admin Error** — Counting or entry mistakes
- **Vendor Error** — Short shipments

### How Detection Works

1. **Expected Inventory** = Starting count + Purchases - Sales
2. **Actual Inventory** = What you count during a scan
3. **Shrinkage** = Expected - Actual

### Reporting Shrinkage

When a scan reveals a discrepancy:

1. You'll see a prompt: "Discrepancy detected"
2. Select the type:
   - Theft
   - Spoilage
   - Damage
   - Admin Error
   - Vendor Error
   - Unknown
3. Add notes (optional)
4. Take a photo as evidence (optional)
5. Submit report

### Viewing Shrinkage Reports

1. Go to **Reports > Shrinkage**
2. Filter by:
   - Date range
   - Location
   - Shrinkage type
   - Item category
3. View totals and trends
4. Export as PDF or CSV

### Reducing Shrinkage

| Type | Prevention Tips |
|------|-----------------|
| **Theft** | Security cameras, bag checks, inventory audits |
| **Spoilage** | FIFO rotation, check expiration dates, proper storage |
| **Damage** | Proper handling training, secure storage |
| **Admin Error** | Double-count verification, barcode scanning |
| **Vendor Error** | Count deliveries, document discrepancies immediately |

---

## 10. Reports & Analytics

### Available Reports

| Report | Description |
|--------|-------------|
| **Inventory Summary** | Current stock levels across all items |
| **Shrinkage Report** | Loss by type, location, and time period |
| **Order History** | All orders with status and totals |
| **Scan Activity** | Who scanned what and when |
| **Below Par Items** | Items needing reorder |
| **Vendor Spending** | Spending by vendor over time |

### Generating Reports

1. Go to **Reports**
2. Select report type
3. Set filters (date range, location, etc.)
4. Tap **Generate**
5. View on screen or export

### Exporting Reports

Reports can be exported as:
- **PDF** — For printing or sharing
- **CSV** — For spreadsheet analysis

### Scheduled Reports

Set up automatic reports:
1. Go to **Settings > Reports**
2. Tap **Schedule Report**
3. Select report type
4. Set frequency (daily, weekly, monthly)
5. Enter email recipients
6. Save

---

## 11. Settings

### Account Settings

- **Profile** — Edit name, email, phone
- **Password** — Change password
- **Notifications** — Configure alerts

### Business Settings

- **Business Info** — Name, address, contact
- **Locations** — Add, edit, remove locations
- **Business Type** — Restaurant, Retail, Warehouse

### Inventory Settings

- **Par Level Defaults** — Default par for new items
- **Categories** — Manage item categories
- **Units** — Configure unit types (each, case, lb, etc.)

### Ordering Settings

- **Auto-Create Orders** — Enable/disable
- **Auto-Approve Threshold** — Amount for auto-approval
- **Daily Limit** — Maximum daily order value
- **Default Vendor** — Preferred vendor for orders

### Team Settings

- **Invite Members** — Add new team members
- **Manage Roles** — Edit permissions
- **Access Logs** — View who accessed what

### API Configuration

- **API URL** — Backend server address
- **Vendor APIs** — Manage vendor connections

---

## 12. Troubleshooting

### Camera Issues

**Problem:** Camera won't scan barcodes

**Solutions:**
1. Check camera permission (Settings > Apps > PROVENIQ Ops > Permissions)
2. Clean camera lens
3. Improve lighting
4. Hold camera 6-12 inches from barcode
5. Try landscape orientation

---

**Problem:** App crashes when opening camera

**Solutions:**
1. Close and reopen app
2. Restart your device
3. Update to latest app version
4. Clear app cache

---

### Sync Issues

**Problem:** Data not syncing

**Solutions:**
1. Check internet connection
2. Pull down to refresh
3. Log out and log back in
4. Check API URL in Settings

---

**Problem:** Orders not appearing

**Solutions:**
1. Refresh the Orders screen
2. Check your role permissions
3. Verify vendor connection
4. Contact support if persists

---

### Vendor Issues

**Problem:** Vendor connection failed

**Solutions:**
1. Verify customer number is correct
2. Check API credentials
3. Contact vendor for API access
4. Try disconnecting and reconnecting

---

**Problem:** Orders rejected by vendor

**Solutions:**
1. Check account standing with vendor
2. Verify item SKUs are correct
3. Check order quantities are valid
4. Contact vendor directly

---

### Login Issues

**Problem:** Can't log in

**Solutions:**
1. Check email and password
2. Use "Forgot Password" to reset
3. Check internet connection
4. Contact support if locked out

---

## 13. Support

### Contact Us

**Email:** support@proveniq.io

**Include in your message:**
- Business name
- Description of issue
- Screenshots (if applicable)
- Device model and OS version

**Response time:** Within 24 hours

### In-App Help

- Tap ⚙️ (Settings) > **Help & FAQ**
- Browse frequently asked questions
- Access this user guide

### Feature Requests

Have an idea? Email us at feedback@proveniq.io

### Report a Bug

Found a bug? Email bugs@proveniq.io with:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Screenshots or video

---

## Appendix A: Keyboard Shortcuts (Tablet)

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + S` | Start scan |
| `Cmd/Ctrl + F` | Search inventory |
| `Cmd/Ctrl + N` | New item |
| `Esc` | Cancel/Back |

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Par Level** | Minimum stock quantity |
| **Reorder Point** | Quantity that triggers reorder |
| **Shrinkage** | Inventory loss |
| **SKU** | Stock Keeping Unit (item identifier) |
| **FIFO** | First In, First Out (rotation method) |
| **Variance** | Difference between expected and actual |

---

**© 2024 PROVENIQ. All rights reserved.**
