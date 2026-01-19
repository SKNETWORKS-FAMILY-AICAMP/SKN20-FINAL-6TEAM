import { useState } from 'react'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center">
      <div className="max-w-2xl w-full p-8">
        <div className="bg-white rounded-lg shadow-lg p-8 text-center">
          <h1 className="text-4xl font-bold text-primary mb-4">
            🚀 BizMate
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            통합 창업/경영 상담 챗봇
          </p>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h3 className="font-semibold text-blue-800">창업</h3>
                <p className="text-sm text-blue-600">Startup</p>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="font-semibold text-green-800">세무/회계</h3>
                <p className="text-sm text-green-600">Tax</p>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <h3 className="font-semibold text-purple-800">지원사업</h3>
                <p className="text-sm text-purple-600">Funding</p>
              </div>
              <div className="bg-orange-50 p-4 rounded-lg">
                <h3 className="font-semibold text-orange-800">노무</h3>
                <p className="text-sm text-orange-600">HR</p>
              </div>
              <div className="bg-red-50 p-4 rounded-lg">
                <h3 className="font-semibold text-red-800">법률</h3>
                <p className="text-sm text-red-600">Legal</p>
              </div>
              <div className="bg-pink-50 p-4 rounded-lg">
                <h3 className="font-semibold text-pink-800">마케팅</h3>
                <p className="text-sm text-pink-600">Marketing</p>
              </div>
            </div>

            <div className="mt-8 pt-8 border-t">
              <p className="text-gray-500 mb-4">React 구동 테스트</p>
              <button
                onClick={() => setCount(count + 1)}
                className="bg-primary text-white px-6 py-3 rounded-lg hover:bg-blue-600 transition-colors"
              >
                카운터: {count}
              </button>
            </div>
          </div>

          <div className="mt-8 text-sm text-gray-500">
            <p>✅ React 18 + TypeScript</p>
            <p>✅ Vite + TailwindCSS</p>
            <p>✅ 프론트엔드 구동 확인 완료</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
