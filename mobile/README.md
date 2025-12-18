# PROVENIQ Ops Mobile

**React Native (Expo) Application**

> Synthetic Eye — AR Inventory Scanner with Bishop Integration

## Status: Future Scope

Mobile UI implementation is **not authorized** in current execution phase.

## Planned Stack

| Component | Technology |
|-----------|------------|
| Framework | React Native (Expo) |
| Camera/AR | `expo-camera` |
| Styling | React Native `StyleSheet` (HUD components) |
| State | Zustand |

## Synthetic Eye Capabilities (Planned)

- **Multi-item detection** per frame
- **Recognition types**: Barcodes, printed labels, product silhouettes
- **Volumetric estimation** for translucent containers
- **HUD overlay**: Bounding boxes, confidence scores, live counts

## Visual Language

- Sci-fi industrial aesthetic
- Android-vision camera overlay
- Clean geometry, no skeuomorphism
- "Knife trick" lock-on behavior

## Bishop Integration

Mobile app will communicate with Bishop FSM via REST API:

```
POST /api/v1/bishop/scan/begin
POST /api/v1/bishop/scan/complete
GET  /api/v1/bishop/status
```

---

**Awaiting authorization to proceed.**
