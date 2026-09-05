import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import CreateTopic from './pages/CreateTopic';
import OutlineApproval from './pages/OutlineApproval';
import TopicView from './pages/TopicView';
import ModuleView from './pages/ModuleView';
import QuizView from './pages/QuizView';
import SessionView from './pages/SessionView';
import Insights from './pages/Insights';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/topics/new" element={<CreateTopic />} />
        <Route path="/topics/:topicId" element={<TopicView />} />
        <Route path="/topics/:topicId/outline" element={<OutlineApproval />} />
        <Route path="/topics/:topicId/modules/:moduleId" element={<ModuleView />} />
        <Route path="/topics/:topicId/modules/:moduleId/quiz" element={<QuizView />} />
        <Route path="/topics/:topicId/modules/:moduleId/session/:sessionId" element={<SessionView />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
