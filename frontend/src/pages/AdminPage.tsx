import React from 'react';
import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Tabs,
  TabsHeader,
  TabsBody,
  Tab,
  TabPanel,
} from '@material-tailwind/react';
import {
  UsersIcon,
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';

const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = React.useState('users');

  const tabs = [
    { value: 'users', label: '회원 관리', icon: UsersIcon },
    { value: 'logs', label: '상담 로그', icon: ChatBubbleLeftRightIcon },
    { value: 'stats', label: '통계', icon: ChartBarIcon },
  ];

  return (
    <div className="p-6">
      <Typography variant="h4" color="blue-gray" className="mb-6">
        관리자
      </Typography>

      <Tabs value={activeTab}>
        <TabsHeader>
          {tabs.map(({ value, label, icon: Icon }) => (
            <Tab key={value} value={value} onClick={() => setActiveTab(value)}>
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4" />
                {label}
              </div>
            </Tab>
          ))}
        </TabsHeader>
        <TabsBody>
          <TabPanel value="users">
            <Card>
              <CardHeader floated={false} shadow={false} className="rounded-none">
                <Typography variant="h6" color="blue-gray">
                  회원 목록
                </Typography>
              </CardHeader>
              <CardBody>
                <div className="text-center py-10 text-gray-500">
                  <Typography>구현 중...</Typography>
                  <Typography variant="small" className="mt-2">
                    회원 목록 조회, 상태 변경 기능이 추가될 예정입니다.
                  </Typography>
                </div>
              </CardBody>
            </Card>
          </TabPanel>

          <TabPanel value="logs">
            <Card>
              <CardHeader floated={false} shadow={false} className="rounded-none">
                <Typography variant="h6" color="blue-gray">
                  상담 로그
                </Typography>
              </CardHeader>
              <CardBody>
                <div className="text-center py-10 text-gray-500">
                  <Typography>구현 중...</Typography>
                  <Typography variant="small" className="mt-2">
                    전체 상담 이력 조회, 검색/필터 기능이 추가될 예정입니다.
                  </Typography>
                </div>
              </CardBody>
            </Card>
          </TabPanel>

          <TabPanel value="stats">
            <Card>
              <CardHeader floated={false} shadow={false} className="rounded-none">
                <Typography variant="h6" color="blue-gray">
                  사용 통계
                </Typography>
              </CardHeader>
              <CardBody>
                <div className="text-center py-10 text-gray-500">
                  <Typography>구현 중...</Typography>
                  <Typography variant="small" className="mt-2">
                    일별/주별/월별 사용 통계, 도메인별 통계가 추가될 예정입니다.
                  </Typography>
                </div>
              </CardBody>
            </Card>
          </TabPanel>
        </TabsBody>
      </Tabs>
    </div>
  );
};

export default AdminPage;
