import { useState, useEffect } from 'react';

// --- Interfaces ---
interface DashboardMatch {
  match_id: number;
  date: string;
  status: string;
  home_goals: number | null;
  away_goals: number | null;
  home: { id?: number; name: string; logo_url: string };
  away: { id?: number; name: string; logo_url: string };
  prediction: { 
    home_win_prob: number; 
    draw_prob: number; 
    away_win_prob: number;
    predicted_home_goals: number;
    predicted_away_goals: number;
  }[] | null;
}

interface TeamStanding {
  id: number;
  name: string;
  logo: string;
  group: string;
  pts: number;
  gf: number;
  ga: number;
  gd: number;
  played: number;
  rank: number;
  advances: boolean;
}

interface Group {
  group: string;
  teams: TeamStanding[];
}

interface BracketMatch {
  id: number;
  home: { id: number; name: string; logo: string };
  away: { id: number; name: string; logo: string };
  pred_hg: number;
  pred_ag: number;
  winner?: { id: number; name: string; logo: string };
}

interface Bracket {
  [round: string]: BracketMatch[];
}

export default function App() {
  // Navigation State
  const [activeTab, setActiveTab] = useState<'daily' | 'tournament'>('daily');
  
  // Daily Feed State
  const [matches, setMatches] = useState<DashboardMatch[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [predictingId, setPredictingId] = useState<number | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);

  // Tournament State
  const [groups, setGroups] = useState<Group[]>([]);
  const [bracket, setBracket] = useState<Bracket | null>(null);
  const [isSimulatingGroups, setIsSimulatingGroups] = useState(false);
  const [isSimulatingKnockouts, setIsSimulatingKnockouts] = useState(false);

  // --- DAILY FEED LOGIC ---
  const fetchMatches = async (dateStr: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/matches?date=${dateStr}`, { cache: 'no-store' });
      const result = await response.json();
      setMatches(result.matches || []);
    } catch (err) {
      console.error(`Failed to load matches for ${dateStr}`, err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'daily') fetchMatches(selectedDate);
  }, [selectedDate, activeTab]);

  const handlePredict = async (matchId: number) => {
    setPredictingId(matchId);
    try {
      await fetch(`http://127.0.0.1:8000/api/matches/${matchId}/predict`, { method: 'POST' });
      await fetchMatches(selectedDate);
    } catch (err) { console.error("Prediction failed", err); } 
    finally { setPredictingId(null); }
  };

  const handleForceSync = async () => {
    setIsSyncing(true);
    try {
      await fetch(`http://127.0.0.1:8000/api/api_update_call?date=${selectedDate}`, { cache: 'no-store' });
      await fetchMatches(selectedDate);
    } catch (err) { console.error("Sync failed", err); } 
    finally { setIsSyncing(false); }
  };

  // --- TOURNAMENT SIMULATOR LOGIC ---
  const handleSimulateGroups = async () => {
    setIsSimulatingGroups(true);
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/tournament/groups`);
      const result = await response.json();
      setGroups(result.groups || []);
      setBracket(null); // Reset bracket when groups change
    } catch (err) { console.error("Group Sim failed", err); }
    finally { setIsSimulatingGroups(false); }
  };

  const handleSimulateKnockouts = async () => {
    setIsSimulatingKnockouts(true);
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/tournament/knockout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ groups })
      });
      const result = await response.json();
      setBracket(result);
    } catch (err) { console.error("Knockout Sim failed", err); }
    finally { setIsSimulatingKnockouts(false); }
  };

  // --- RENDER HELPERS ---
  const renderDailyFeed = () => (
    <>
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '15px', backgroundColor: '#fff', padding: '15px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', border: '1px solid #eaeaea', flexWrap: 'wrap', marginBottom: '40px' }}>
        <label htmlFor="date-picker" style={{ fontWeight: 'bold', color: '#34495e' }}>Select Match Day:</label>
        <input id="date-picker" type="date" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)} style={{ padding: '10px', borderRadius: '8px', border: '1px solid #bdc3c7', fontSize: '16px', outline: 'none', cursor: 'pointer' }} />
        <button onClick={handleForceSync} disabled={isSyncing} style={{ padding: '10px 20px', backgroundColor: isSyncing ? '#95a5a6' : '#2ecc71', color: 'white', border: 'none', borderRadius: '8px', cursor: isSyncing ? 'not-allowed' : 'pointer', fontWeight: 'bold', fontSize: '14px', transition: 'background-color 0.2s' }}>
          {isSyncing ? 'Syncing...' : 'Force API Sync'}
        </button>
      </div>

      {isLoading ? ( <div style={{ textAlign: 'center', color: '#7f8c8d' }}>Loading matches...</div> ) 
      : matches.length === 0 ? ( <div style={{ textAlign: 'center', color: '#7f8c8d', padding: '40px', backgroundColor: '#fff', borderRadius: '12px' }}>No matches found.</div> ) 
      : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '20px' }}>
          {matches.map(match => {
            let pred: any = null;
            if (Array.isArray(match.prediction) && match.prediction.length > 0) pred = match.prediction[0];
            else if (match.prediction && !Array.isArray(match.prediction)) pred = match.prediction;
            
            const isUpcoming = match.status === 'NS';
            const matchTime = new Date(match.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            return (
              <div key={match.match_id} style={{ backgroundColor: '#fff', padding: '20px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', border: '1px solid #eaeaea' }}>
                <div style={{ textAlign: 'center', marginBottom: '15px', fontSize: '12px', fontWeight: 'bold', color: isUpcoming ? '#95a5a6' : '#e74c3c', textTransform: 'uppercase' }}>
                  {isUpcoming ? 'Upcoming' : match.status === 'FT' || match.status === 'PEN' ? 'Full Time' : `Live: ${match.status}`}
                  <span style={{ margin: '0 8px', color: '#bdc3c7' }}>•</span><span style={{ color: '#34495e' }}>{matchTime}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <div style={{ textAlign: 'center', flex: 1 }}><img src={match.home.logo_url} alt={match.home.name} style={{height: '50px', objectFit: 'contain' }} /><div style={{ fontWeight: 'bold', fontSize: '16px', marginTop: '8px', color: '#2c3e50' }}>{match.home.name}</div></div>
                  <div style={{ fontSize: '32px', fontWeight: '900', padding: '0 20px', color: '#2c3e50', letterSpacing: '2px' }}>{isUpcoming ? 'vs' : `${match.home_goals || 0} - ${match.away_goals || 0}`}</div>
                  <div style={{ textAlign: 'center', flex: 1 }}><img src={match.away.logo_url} alt={match.away.name} style={{ height: '50px', objectFit: 'contain' }} /><div style={{ fontWeight: 'bold', fontSize: '16px', marginTop: '8px', color: '#2c3e50' }}>{match.away.name}</div></div>
                </div>
                <div style={{ borderTop: '1px solid #f1f2f6', paddingTop: '15px', color:'black' }}>
                  {pred ? (
                    <div style={{ fontSize: '14px', textAlign: 'center' }}>
                      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '10px', color: '#7f8c8d', marginBottom: '8px', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                        <span>AI Prediction</span><span style={{ backgroundColor: '#2c3e50', color: '#fff', padding: '3px 8px', borderRadius: '12px', fontWeight: 'bold' }}>Score: {pred.predicted_home_goals} - {pred.predicted_away_goals}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', backgroundColor: '#f8f9fa', padding: '10px', borderRadius: '8px' }}>
                        <span style={{ color: '#2ecc71', fontWeight: '800' }}>{match.home.name}: {(pred.home_win_prob * 100).toFixed(1)}%</span>
                        <span style={{ color: '#95a5a6', fontWeight: '600' }}>Draw: {(pred.draw_prob * 100).toFixed(1)}%</span>
                        <span style={{ color: '#e74c3c', fontWeight: '800' }}>{match.away.name}: {(pred.away_win_prob * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                  ) : (
                    <button onClick={() => handlePredict(match.match_id)} disabled={predictingId === match.match_id} style={{ width: '100%', padding: '12px', backgroundColor: '#2980b9', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', fontSize: '14px' }}>
                      {predictingId === match.match_id ? 'Calculating...' : 'Generate Prediction'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );

  const renderTournamentPredictor = () => (
    <div style={{width: "100%"}}>
      <div style={{ textAlign: 'center', marginBottom: '30px' }}>
        <button onClick={handleSimulateGroups} disabled={isSimulatingGroups} style={{ padding: '15px 30px', backgroundColor: '#8e44ad', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', fontSize: '16px' }}>
          {isSimulatingGroups ? 'Running Local ML Simulation...' : '1. Predict Full Group Stage'}
        </button>
      </div>

      {groups.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px', marginBottom: '40px' }}>
          {groups.map(g => (
            <div key={g.group} style={{ backgroundColor: '#fff', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', overflow: 'hidden' }}>
              <div style={{ backgroundColor: '#2c3e50', color: '#fff', padding: '10px', textAlign: 'center', fontWeight: 'bold' }}>Group {g.group}</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8f9fa', color: '#7f8c8d' }}>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Team</th>
                    <th>P</th><th>GD</th><th>Pts</th>
                  </tr>
                </thead>
                <tbody>
                  {g.teams.map((t, idx) => (
                    <tr key={t.id} style={{ borderTop: '1px solid #eaeaea', backgroundColor: t.advances ? '#e8f8f5' : '#fff' }}>
                      <td style={{ padding: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 'bold', width: '15px', color: '#95a5a6' }}>{t.rank}</span>
                        <img src={t.logo} alt="" style={{ height: '20px', width: '20px', objectFit: 'contain' }} />
                        <span style={{ fontWeight: t.advances ? 'bold' : 'normal', color: '#2c3e50' }}>{t.name}</span>
                      </td>
                      <td style={{ textAlign: 'center', color: '#7f8c8d' }}>{t.played}</td>
                      <td style={{ textAlign: 'center', color: '#7f8c8d' }}>{t.gd > 0 ? `+${t.gd}` : t.gd}</td>
                      <td style={{ textAlign: 'center', fontWeight: 'bold', color: '#2980b9' }}>{t.pts}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}

      {groups.length > 0 && (
        <div style={{ textAlign: 'center', marginBottom: '40px', borderTop: '2px dashed #eaeaea', paddingTop: '30px' }}>
          <button onClick={handleSimulateKnockouts} disabled={isSimulatingKnockouts} style={{ padding: '15px 30px', backgroundColor: '#e67e22', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', fontSize: '16px' }}>
            {isSimulatingKnockouts ? 'Mapping Combinations...' : '2. Predict Knockout Bracket'}
          </button>
        </div>
      )}

      {bracket && (
        <div style={{ display: 'flex', overflowX: 'auto', gap: '40px', paddingBottom: '20px' }}>
          {['Round of 32', 'Round of 16', 'Quarter-Finals', 'Semi-Finals', 'Final'].map((roundName) => (
            <div key={roundName} style={{ minWidth: '250px', display: 'flex', flexDirection: 'column', gap: '20px', justifyContent: 'space-around' }}>
              <h3 style={{ textAlign: 'center', color: '#2c3e50', fontSize: '16px', marginBottom: '10px' }}>{roundName}</h3>
              {bracket[roundName].map((m: BracketMatch, i: number) => (
                <div key={i} style={{ backgroundColor: '#fff', border: '1px solid #bdc3c7', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 2px 5px rgba(0,0,0,0.05)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderBottom: '1px solid #eaeaea', backgroundColor: m.winner?.id === m.home.id ? '#e8f8f5' : '#fff' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {m.home.logo && <img src={m.home.logo} alt="" style={{ height: '16px', width: '16px' }}/>}
                      <span style={{ fontWeight: m.winner?.id === m.home.id ? 'bold' : 'normal', color: '#2c3e50', fontSize: '14px' }}>{m.home.name}</span>
                    </div>
                    <span style={{ fontWeight: 'bold', color: '#2980b9' }}>{m.pred_hg}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', backgroundColor: m.winner?.id === m.away.id ? '#e8f8f5' : '#fff' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {m.away.logo && <img src={m.away.logo} alt="" style={{ height: '16px', width: '16px' }}/>}
                      <span style={{ fontWeight: m.winner?.id === m.away.id ? 'bold' : 'normal', color: '#2c3e50', fontSize: '14px' }}>{m.away.name}</span>
                    </div>
                    <span style={{ fontWeight: 'bold', color: '#2980b9' }}>{m.pred_ag}</span>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div style={{width: '100vw', fontFamily: 'system-ui, sans-serif', backgroundColor: '#f8f9fa', minHeight: '100vh', padding: '40px 20px' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto', marginBottom: '20px' }}>
        <h1 style={{ textAlign: 'center', color: '#2c3e50', marginBottom: '30px' }}>AI World Cup Simulator</h1>
        
        {/* TAB NAVIGATION */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginBottom: '40px' }}>
          <button onClick={() => setActiveTab('daily')} style={{ padding: '12px 24px', backgroundColor: activeTab === 'daily' ? '#2c3e50' : '#ecf0f1', color: activeTab === 'daily' ? 'white' : '#7f8c8d', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', transition: '0.2s' }}>
            Daily Games Feed
          </button>
          <button onClick={() => setActiveTab('tournament')} style={{ padding: '12px 24px', backgroundColor: activeTab === 'tournament' ? '#2c3e50' : '#ecf0f1', color: activeTab === 'tournament' ? 'white' : '#7f8c8d', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', transition: '0.2s' }}>
            Predict Tournament Bracket
          </button>
        </div>
      </div>
      
      <div style={{ maxWidth: '90vw', margin: '0 auto' }}>
        {activeTab === 'daily' ? renderDailyFeed() : renderTournamentPredictor()}
      </div>
    </div>
  );
}