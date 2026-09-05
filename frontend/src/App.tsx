import './App.css'

const marketOverview = [
  { label: 'S&P 500', value: '5,432.18', change: '+0.82%' },
  { label: 'NASDAQ', value: '17,861.32', change: '+1.14%' },
  { label: 'DOW', value: '39,804.50', change: '+0.41%' },
]

const recentSignals = [
  { symbol: 'AAPL', signal: 'Bullish', strength: 'Strong' },
  { symbol: 'MSFT', signal: 'Neutral', strength: 'Moderate' },
  { symbol: 'NVDA', signal: 'Bullish', strength: 'Strong' },
  { symbol: 'TSLA', signal: 'Bearish', strength: 'Cautious' },
]

function App() {
  return (
    <div className="dashboard-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Decision support</p>
          <h1>TradingGuard</h1>
        </div>
        <div className="status-badge">Paper Trading Active</div>
      </header>

      <main className="dashboard-grid">
        <section className="card span-2">
          <div className="card-header">
            <h2>Market Overview</h2>
            <span>Updated 5 min ago</span>
          </div>
          <div className="market-list">
            {marketOverview.map((item) => (
              <div key={item.label} className="market-row">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <em>{item.change}</em>
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <h2>Signal Score</h2>
          </div>
          <div className="metric-value">72</div>
          <p className="metric-label">Risk-adjusted signal confidence</p>
        </section>

        <section className="card">
          <div className="card-header">
            <h2>Risk Level</h2>
          </div>
          <div className="metric-value risk">Balanced</div>
          <p className="metric-label">Exposure capped at 20%</p>
        </section>

        <section className="card span-2">
          <div className="card-header">
            <h2>Paper Trading status</h2>
          </div>
          <div className="paper-status">
            <div>
              <span className="label">Portfolio Value</span>
              <strong>$128,460</strong>
            </div>
            <div>
              <span className="label">Daily P/L</span>
              <strong className="positive">+$1,240</strong>
            </div>
            <div>
              <span className="label">Orders</span>
              <strong>8 active</strong>
            </div>
          </div>
        </section>

        <section className="card span-2">
          <div className="card-header">
            <h2>Recent Signals</h2>
          </div>
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Signal</th>
                <th>Strength</th>
              </tr>
            </thead>
            <tbody>
              {recentSignals.map((item) => (
                <tr key={item.symbol}>
                  <td>{item.symbol}</td>
                  <td>{item.signal}</td>
                  <td>{item.strength}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  )
}

export default App
