import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import { LoginPage } from '@/pages/Login';
import { WorkbenchPage } from '@/pages/Workbench';
import { DevicesPage } from '@/pages/Devices';
import { AlarmsPage } from '@/pages/Alarms';
import { DefectsPage } from '@/pages/Defects';
import { WorkOrdersPage } from '@/pages/WorkOrders';
import { RunsPage } from '@/pages/Runs';
import { KnowledgePage } from '@/pages/Knowledge';
import { ReviewCasesPage } from '@/pages/ReviewCases';
import { HealthPage } from '@/pages/Health';
import { MetricsPage } from '@/pages/Metrics';
import { ToolsPage } from '@/pages/Tools';
import { SettingsPage } from '@/pages/Settings';
import { RequireAuth } from '@/components/RequireAuth';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/workbench" replace />} />
        <Route path="/workbench" element={<WorkbenchPage />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/alarms" element={<AlarmsPage />} />
        <Route path="/defects" element={<DefectsPage />} />
        <Route path="/workorders" element={<WorkOrdersPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/review-cases" element={<ReviewCasesPage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/workbench" replace />} />
      </Route>
    </Routes>
  );
}
