import Navbar from './Navbar';
import KibanaDashboard from './KibanaDashboard';

export default function DashboardPage() {
  return (
    <div className="h-screen w-full flex flex-col bg-gradient-to-b from-orange-50/50 to-white overflow-hidden">
      <Navbar />
      <div className="flex-1 min-h-0">
        <KibanaDashboard />
      </div>
    </div>
  );
}

