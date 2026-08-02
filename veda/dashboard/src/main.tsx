// VEDA dashboard — live device cloud, universal notifications, control + consent.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { DashboardApp } from './DashboardApp';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <React.StrictMode><DashboardApp /></React.StrictMode>
);