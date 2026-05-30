import Navbar from './Navbar';
import KibanaDashboard from './KibanaDashboard';
import { useAuth } from '../context/AuthContext';
import { KIBANA_DASHBOARD_N12_EMBED_URL, KIBANA_DASHBOARD_N3_BASE_URL } from '../config';

export default function DashboardPage() {
  const { role } = useAuth();
  const n12 = role === 'N1' || role === 'N2';

  return (
    <div className="h-screen w-full flex flex-col bg-gradient-to-b from-orange-50/50 to-white overflow-hidden">
      <Navbar />
      <div className="flex-1 min-h-0">
        <KibanaDashboard baseUrl={n12 ? KIBANA_DASHBOARD_N12_EMBED_URL : KIBANA_DASHBOARD_N3_BASE_URL} />
      </div>
    </div>
  );
}

