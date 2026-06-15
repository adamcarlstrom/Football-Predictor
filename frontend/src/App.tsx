import { useState, useEffect } from 'react';

// 1. Types: We define the shape of the data we expect from the Python backend.
// This gives us autocomplete and prevents typos.
interface PredictionData {
  match_info: {
    match_id: number;
    home_team_name: string;
    away_team_name: string;
    status: string;
  };
  prediction: {
    home_win_prob: number;
    draw_prob: number;
    away_win_prob: number;
  };
}

interface MatchOption {
  match_id: number;
  label: string;
}

export default function App() {
  // 2. State Hooks: React's memory. 
  // 'matchId' tracks what the user types in the input box.
  const [matchId, setMatchId] = useState<string>('718243'); // Using a default ID for testing
  
  // These track the network request lifecycle
  const [data, setData] = useState<PredictionData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // To hold list of matches
  const [availableMatches, setAvailableMatches] = useState<MatchOption[]>([]);
  const [isLoadingMatches, setIsLoadingMatches] = useState<boolean>(true);

  useEffect(() => {
    const fetchDropdownData = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/matches/today');
        const result = await response.json();
        setAvailableMatches(result.matches);
        // Auto-select the first match in the list if it exists
        if (result.matches.length > 0) {
          setMatchId(result.matches[0].match_id.toString());
        }
      } catch (err) {
        console.error("Failed to load matches for dropdown", err);
      } finally {
        setIsLoadingMatches(false);
      }
    };

    fetchDropdownData();
  }, []); // The empty array [] means this only runs once on load

  // 3. The Action Function: Triggered when the button is clicked.
  const fetchPrediction = async () => {
    if (!matchId) return;

    // Reset previous states before starting a new request
    setIsLoading(true);
    setError(null);
    setData(null);

    try {
      // 4. The Network Call: Hitting your local FastAPI server.
      const response = await fetch(`http://127.0.0.1:8000/api/matches/${matchId}/predict`, {
        method: 'POST', 
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Backend returned status: ${response.status}`);
      }

      // 5. Updating State: This triggers a re-render to show the new data
      const jsonData = await response.json();
      setData(jsonData);
      
    } catch (err: any) {
      setError(err.message || 'Failed to fetch prediction');
    } finally {
      // Whether it succeeded or failed, we are no longer loading
      setIsLoading(false);
    }
  };

  // 6. The UI Render: This uses conditional rendering.
  // It checks the state variables to decide what HTML to show.
  return (
    <div style={{ padding: '40px', fontFamily: 'system-ui, sans-serif', maxWidth: '600px', margin: '0 auto' }}>
      <h1>Match Predictor</h1>
      <p>Showing todays matches</p>
      <div style={{ marginBottom: '20px', display: 'flex', gap: '10px' }}>
        
        {/* THE NEW DROPDOWN MENU */}
        <select 
          value={matchId} 
          onChange={(e) => setMatchId(e.target.value)}
          disabled={isLoadingMatches}
          style={{ padding: '8px', width: '300px' }}
        >
          {isLoadingMatches ? (
            <option>Loading today's matches...</option>
          ) : (
            availableMatches.map((match) => (
              <option key={match.match_id} value={match.match_id}>
                {match.label}
              </option>
            ))
          )}
        </select>

        <button 
          onClick={fetchPrediction} 
          disabled={isLoading || !matchId}
          style={{ padding: '8px 16px', cursor: 'pointer' }}
        >
          {isLoading ? 'Calculating...' : 'Predict Outcome'}
        </button>
      </div>

      {/* CONDITIONAL RENDERING: Only show this div if we successfully got data */}
      {data && (
        <div style={{ padding: '20px', border: '1px solid #ccc', borderRadius: '8px', marginTop: '20px' }}>
          <h2>{data.match_info.home_team_name} vs {data.match_info.away_team_name}</h2>
          <p>Status: {data.match_info.status}</p>
          
          <hr style={{ margin: '20px 0' }} />
          
          <h3>ML Model Probabilities</h3>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            <li style={{ marginBottom: '10px' }}>
              <strong>Home Win:</strong> {(data.prediction.home_win_prob * 100).toFixed(1)}%
            </li>
            <li style={{ marginBottom: '10px' }}>
              <strong>Draw:</strong> {(data.prediction.draw_prob * 100).toFixed(1)}%
            </li>
            <li style={{ marginBottom: '10px' }}>
              <strong>Away Win:</strong> {(data.prediction.away_win_prob * 100).toFixed(1)}%
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}