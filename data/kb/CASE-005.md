---
title: Case study - fleet telemetry platform for Caspian Freight Lines
section: Case studies
language: en
effective_date: 2025-10-28
format: md
doc_id: CASE-005
---

# Case study - fleet telemetry platform for Caspian Freight Lines

## Customer and challenge

Caspian Freight Lines is a fictional road freight operator with 8,500 trucks. The customer wanted to receive telemetry from vehicles in real time, to track routes and to detect unsafe driving. The project took 8 months, from March to October 2025.

## Solution

Vehicle trackers send data over MQTT. Messages are processed by .NET 8 services and stored in PostgreSQL with the TimescaleDB extension. The platform accepts up to 12,000 messages per second. A web application shows vehicles on a map and a mobile application is provided for drivers. Alerts are delivered by push notifications within 5 seconds after the event.

## Team

Nine people worked on the project: 5 developers, 1 QA engineer, 1 DevOps engineer, 1 business analyst and 1 project manager.

## Results

Fuel consumption reports became available daily instead of monthly. Unsafe driving events fell by 23% in six months. The platform has been running with an availability of 99.9% since the launch in October 2025.
