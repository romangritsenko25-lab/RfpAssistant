---
title: Case study - data platform for Eurasia Retail Group
section: Case studies
language: en
effective_date: 2025-05-12
format: pdf
doc_id: CASE-004
---

# Case study - data platform for Eurasia Retail Group

## Customer and challenge

Eurasia Retail Group is a fictional retail chain with 310 stores in Kazakhstan and Uzbekistan. In 2024 the customer needed a single data platform for sales analytics and demand forecasting, replacing spreadsheets prepared manually by regional teams. The project ran for 10 months, from January to October 2024.

## Solution

Sales events from cash registers are streamed through Apache Kafka into a data lake, processed with Apache Spark and loaded into ClickHouse for reporting. The platform processes about 2 TB of data per day. Forecasting models are written in Python and managed with MLflow. Dashboards are built in Apache Superset.

## Team

The team had 12 people: 4 data engineers, 3 machine learning engineers, 2 analysts, 1 DevOps engineer, 1 QA engineer and 1 project manager.

## Results

The weighted mean absolute percentage error (WMAPE) of weekly demand forecasts decreased from 21% to 13%. Preparation of the weekly sales report was reduced from 2 working days to 15 minutes. Out-of-stock situations in the pilot group of 40 stores decreased by 17%.
