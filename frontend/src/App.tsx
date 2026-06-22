import { useState, useEffect } from 'react';

interface DashboardMatch {
  match_id: number;
  date: string;
  status: string;
  home_goals: number | null;
  away_goals: number | null;
  home: { name: string; logo_url: string };
  away: { name: string; logo_url: string };
  prediction: { 
    home_win_prob: number; 
    draw_prob: number; 
    away_win_prob: number;
    predicted_home_goals: number;
    predicted_away_goals: number;
  }[] | null;
}

export default function App() {
  const [matches, setMatches] = useState<DashboardMatch[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [predictingId, setPredictingId] = useState<number | null>(null);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  
  // State to track the currently selected date (Defaults to today in YYYY-MM-DD format)
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);

  // Function now accepts the date parameter
  const fetchMatches = async (dateStr: string) => {
    setIsLoading(true);
    try {
      // Added the 'cache' property to bypass the browser's aggressive caching
      console.log("Fetching matches by date")
      const response = await fetch(`http://127.0.0.1:8000/api/matches?date=${dateStr}`, {
        cache: 'no-store' 
      });
      const result = await response.json();
      console.log(result)
      setMatches(result.matches || []);
    } catch (err) {
      console.error(`Failed to load matches for ${dateStr}`, err);
    } finally {
      setIsLoading(false);
    }
  };

  // The dependency array now includes selectedDate. 
  // If the user changes the date, this automatically re-runs.
  useEffect(() => {
    fetchMatches(selectedDate);
  }, [selectedDate]);

  const handlePredict = async (matchId: number) => {
    setPredictingId(matchId);
    try {
      console.log("Predicting match")
      await fetch(`http://127.0.0.1:8000/api/matches/${matchId}/predict`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      await fetchMatches(selectedDate); // Refresh current date's view
    } catch (err) {
      console.error("Prediction failed", err);
    } finally {
      setPredictingId(null);
    }
  };

  const reloadAPICall = async () => {
    setIsSyncing(true);
    try {
      console.log("Forcing API sync to fetch missing matches")
      await fetch(`http://127.0.0.1:8000/api/api_update_call?date=${selectedDate}`, {
        cache: 'no-store'
      });
      await fetchMatches(selectedDate); // Refresh current date's view
    } catch (err) {
      console.error("API Update failed", err);
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div style={{width: '100vw', fontFamily: 'system-ui, sans-serif', backgroundColor: '#f8f9fa', minHeight: '100vh', padding: '40px 20px' }}>
      
      {/* HEADER & DATE CONTROLS */}
      <div style={{ maxWidth: '1000px', margin: '0 auto', marginBottom: '40px' }}>
        <h1 style={{ textAlign: 'center', color: '#2c3e50', marginBottom: '20px' }}>World Cup Match Predictor</h1>
        
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '15px', backgroundColor: '#fff', padding: '15px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', border: '1px solid #eaeaea' }}>
          <label htmlFor="date-picker" style={{ fontWeight: 'bold', color: '#34495e' }}>Select Match Day:</label>
          <input 
            id="date-picker"
            type="date" 
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            style={{ padding: '10px', borderRadius: '8px', border: '1px solid #bdc3c7', fontSize: '16px', outline: 'none', cursor: 'pointer' }}
          />
          <button 
          onClick={() => reloadAPICall()}
          style={{padding: '12px', backgroundColor: '#2980b9', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', fontSize: '14px' }}
        >
          Reload API Call
        </button>
        </div>
      </div>
      
      {/* MATCH FEED */}
      <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
        {isLoading ? (
          <div style={{ textAlign: 'center', color: '#7f8c8d' }}>Loading matches for {selectedDate}...</div>
        ) : matches.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#7f8c8d', padding: '40px', backgroundColor: '#fff', borderRadius: '12px' }}>
            No World Cup matches found on {selectedDate}.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '20px' }}>
            {/* NEW: CSS Grid layout for 2+ cards per row */}
            {matches.map(match => {
              let pred: any = null;
              if (Array.isArray(match.prediction) && match.prediction.length > 0) {
                pred = match.prediction[0]; // Extract from Array
              } else if (match.prediction && !Array.isArray(match.prediction)) {
                pred = match.prediction; // Extract directly from Object
              }
              const isUpcoming = match.status === 'NS';
              const homeScore = match.home_goals !== null ? match.home_goals : '0';
              const awayScore = match.away_goals !== null ? match.away_goals : '0';
              
              // NEW: Extract clean local time from ISO string
              const matchTime = new Date(match.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

              return (
                <div key={match.match_id} style={{ backgroundColor: '#fff', padding: '20px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', border: '1px solid #eaeaea' }}>
                  
                  {/* Match Status & Time Header */}
                  <div style={{ textAlign: 'center', marginBottom: '15px', fontSize: '12px', fontWeight: 'bold', color: isUpcoming ? '#95a5a6' : '#e74c3c', textTransform: 'uppercase' }}>
                    {isUpcoming ? 'Upcoming' : match.status === 'FT' || match.status === 'PEN' ? 'Full Time' : `Live: ${match.status}`}
                    <span style={{ margin: '0 8px', color: '#bdc3c7' }}>•</span>
                    <span style={{ color: '#34495e' }}>{matchTime}</span>
                  </div>

                  {/* Teams and Actual Scoreline */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <div style={{ textAlign: 'center', flex: 1 }}>
                      <img src={match.home.logo_url} alt={match.home.name} style={{height: '50px', objectFit: 'contain' }} />
                      <div style={{ fontWeight: 'bold', fontSize: '16px', marginTop: '8px', color: '#2c3e50' }}>{match.home.name}</div>
                    </div>
                    
                    <div style={{ fontSize: '32px', fontWeight: '900', padding: '0 20px', color: '#2c3e50', letterSpacing: '2px' }}>
                       {isUpcoming ? 'vs' : `${homeScore} - ${awayScore}`}
                    </div>

                    <div style={{ textAlign: 'center', flex: 1 }}>
                      <img src={match.away.logo_url} alt={match.away.name} style={{ height: '50px', objectFit: 'contain' }} />
                      <div style={{ fontWeight: 'bold', fontSize: '16px', marginTop: '8px', color: '#2c3e50' }}>{match.away.name}</div>
                    </div>
                  </div>

                  {/* AI Prediction Section */}
                  <div style={{ borderTop: '1px solid #f1f2f6', paddingTop: '15px', color:'black' }}>
                    {pred ? (
                      <div style={{ fontSize: '14px', textAlign: 'center' }}>
                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '10px', color: '#7f8c8d', marginBottom: '8px', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                          <span>AI Prediction</span>
                          <span style={{ backgroundColor: '#2c3e50', color: '#fff', padding: '3px 8px', borderRadius: '12px', fontWeight: 'bold' }}>
                            Score: {pred.predicted_home_goals} - {pred.predicted_away_goals}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', backgroundColor: '#f8f9fa', padding: '10px', borderRadius: '8px' }}>
                          <span style={{ color: '#2ecc71', fontWeight: '800' }}>{match.home.name}: {(pred.home_win_prob * 100).toFixed(1)}%</span>
                          <span style={{ color: '#95a5a6', fontWeight: '600' }}>Draw: {(pred.draw_prob * 100).toFixed(1)}%</span>
                          <span style={{ color: '#e74c3c', fontWeight: '800' }}>{match.away.name}: {(pred.away_win_prob * 100).toFixed(1)}%</span>
                        </div>
                      </div>
                    ) : (
                      <button 
                        onClick={() => handlePredict(match.match_id)}
                        disabled={predictingId === match.match_id}
                        style={{ width: '100%', padding: '12px', backgroundColor: '#2980b9', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', fontSize: '14px' }}
                      >
                        {predictingId === match.match_id ? 'Calculating AI Prediction...' : 'Generate Prediction'}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}