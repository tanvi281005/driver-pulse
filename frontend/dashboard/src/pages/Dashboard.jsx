import { useEffect, useState, useRef } from "react"
import axios from "axios"
{/*import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts"*/}
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"

function Dashboard({driver}){

  const [trips,setTrips] = useState([])
  const [earnings,setEarnings] = useState([])
  const [earningsSeries, setEarningsSeries] = useState([])
  const [stressData,setStressData] = useState([])
  const [flagged,setFlagged] = useState([])
  const [goal,setGoal] = useState(null)

  const [activeTrip,setActiveTrip] = useState(null)
  const [tripRunning,setTripRunning] = useState(false)
  const [liveEvents,setLiveEvents] = useState([])

  const intervalRef = useRef(null)

  useEffect(()=>{

    loadTrips()
    loadEarnings()
    loadEarningsGraph()
    loadFlagged()
    loadGoal()

  },[])


  const loadTrips = async () => {

    const res = await axios.get(
      `http://localhost:8000/driver_trips/${driver.driver_id}`
    )

    setTrips(res.data)

  }


  const loadEarnings = async () => {

    const res = await axios.get(
      `http://localhost:8000/earnings/${driver.driver_id}`
    )

    setEarnings(res.data)

  }

  const loadEarningsGraph = async () => {
    const res=await axios.get(`http://localhost:8000/earnings_graph/${driver.driver_id}`)
    setEarningsSeries(res.data.series || [])
  }

  const loadFlagged = async () => {

    const res = await axios.get(
      `http://localhost:8000/flagged_events/${driver.driver_id}`
    )

    setFlagged(res.data)

  }


  const loadGoal = async () => {

    const res = await axios.get(
      `http://localhost:8000/goal_prediction/${driver.driver_id}`
    )

    setGoal(res.data.probability)

  }


  const startTrip = async () => {

    const res = await axios.post(
      `http://localhost:8000/start_trip/${driver.driver_id}`
    )

    const tripId = res.data.trip_id

    setActiveTrip(tripId)
    setTripRunning(true)

    startSimulation(tripId)

  }


  const startSimulation = (tripId) => {

    intervalRef.current = setInterval(async () => {

      const res = await axios.get(
        `http://localhost:8000/trip_step/${tripId}`
      )

      const motion = res.data.motion
      const audio = res.data.audio

      if(audio){

        const stressValue = audio.audio_level_db / 100

        setStressData(prev => [
          ...prev,
          {
            time: prev.length,
            stress: stressValue
          }
        ])

        if(audio.audio_level_db > 85){

          setLiveEvents(prev => [
            ...prev,
            {
              time: prev.length,
              type: audio.audio_classification,
              db: audio.audio_level_db
            }
          ])

        }

      }

    },1000)

  }

  {/*
  const endTrip = async () => {

    clearInterval(intervalRef.current)

    const earningsInput = prompt("Enter trip earnings")

    await axios.post(
      `http://localhost:8000/end_trip/${activeTrip}`
    )

    setTripRunning(false)
    setActiveTrip(null)

    alert("Trip completed")

    loadTrips()
    loadEarnings()

  }*/}

  const endTrip = async () => {
    clearInterval(intervalRef.current)
    const earningsInput = prompt("Enter trip earnings")
    
    await axios.post(`http://localhost:8000/end_trip/${activeTrip}`)

    setTripRunning(false)
    setActiveTrip(null)

    alert("Trip completed")

    loadTrips()
    loadEarnings()
    loadEarningsGraph()
    loadGoal()
    loadFlagged()
  }

  const latestCumulative =
    earnings.length > 0
      ? Number(earnings[earnings.length - 1].cumulative_earnings || 0)
      : 0

  const statusColor =
    goalData?.status === "ON_TRACK"
      ? "green"
      : goalData?.status === "CLOSE"
      ? "orange"
      : "red"

  {/*
  return(

    <div style={{padding:40}}>

      <h2>Welcome {driver.name}</h2>


      <div style={{marginBottom:20}}>

        {!tripRunning && (
          <button onClick={startTrip}>
            Start Trip
          </button>
        )}

        {tripRunning && (
          <button onClick={endTrip}>
            End Trip
          </button>
        )}

      </div>


      <h3>Trips Today</h3>

      {trips.map(t => (
        <div key={t.trip_id}>
          {t.trip_id} | {t.distance_km} km
        </div>
      ))}


      <h3>Stress Timeline</h3>

      <LineChart width={600} height={300} data={stressData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="time"/>
        <YAxis/>
        <Tooltip/>
        <Line type="monotone" dataKey="stress" stroke="#ff0000"/>
      </LineChart>


      <h3>Live Stress Events</h3>

      {liveEvents.slice(-5).map((e,i)=>(
        <div key={i}>
          {e.type} ({e.db} dB)
        </div>
      ))}


      <h3>Earnings</h3>

      {earnings.map(e => (
        <div key={e.trip_id}>
          {e.trip_id} : ₹{e.fare}
        </div>
      ))}


      <h3>Goal Prediction</h3>

      <div>
        Probability of reaching goal today: {goal}
      </div>


      <h3>Flagged Stress Moments</h3>

      {flagged.slice(0,10).map(f => (
        <div key={f.timestamp}>
          {f.trip_id} | {f.severity} | {f.explanation}
        </div>
      ))}

    </div>

  )

}
*/}

  return (
    <div style={{ padding: 40, width: "100%", maxWidth: 1200, margin: "0 auto" }}>
      <h2>Welcome {driver.name}</h2>

      <div style={{ marginBottom: 20 }}>
        {!tripRunning && <button onClick={startTrip}>Start Trip</button>}
        {tripRunning && <button onClick={endTrip}>End Trip</button>}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 16,
          marginBottom: 30,
        }}
      >
        <div style={{ padding: 16, border: "1px solid #ccc", borderRadius: 12 }}>
          <h4>Total Earnings</h4>
          <div style={{ fontSize: 24, fontWeight: "bold" }}>₹{latestCumulative.toFixed(2)}</div>
        </div>

        <div style={{ padding: 16, border: "1px solid #ccc", borderRadius: 12 }}>
          <h4>Target Earnings</h4>
          <div style={{ fontSize: 24, fontWeight: "bold" }}>
            ₹{goalData ? Number(goalData.target_earnings || 0).toFixed(2) : "0.00"}
          </div>
        </div>

        <div style={{ padding: 16, border: "1px solid #ccc", borderRadius: 12 }}>
          <h4>Projected Final</h4>
          <div style={{ fontSize: 24, fontWeight: "bold" }}>
            ₹{goalData ? Number(goalData.projected_final_earnings || 0).toFixed(2) : "0.00"}
          </div>
        </div>

        <div style={{ padding: 16, border: "1px solid #ccc", borderRadius: 12 }}>
          <h4>Goal Probability</h4>
          <div style={{ fontSize: 24, fontWeight: "bold" }}>
            {goalData ? `${(Number(goalData.probability || 0) * 100).toFixed(1)}%` : "0.0%"}
          </div>
          <div style={{ marginTop: 8, color: statusColor, fontWeight: "bold" }}>
            {goalData ? goalData.status : "NO_DATA"}
          </div>
        </div>
      </div>

      {goalData && (
        <div style={{ marginBottom: 30, padding: 16, border: "1px solid #ccc", borderRadius: 12 }}>
          <h3>Goal Prediction Details</h3>
          <div>Current Earnings: ₹{Number(goalData.current_earnings || 0).toFixed(2)}</div>
          <div>Elapsed Hours: {Number(goalData.elapsed_hours || 0).toFixed(2)}</div>
          <div>Current Velocity: ₹{Number(goalData.current_velocity || 0).toFixed(2)}/hour</div>
          <div>Target Velocity: ₹{Number(goalData.target_velocity || 0).toFixed(2)}/hour</div>
          <div>Remaining Hours: {Number(goalData.remaining_hours || 0).toFixed(2)}</div>
          <div>Earnings Gap: ₹{Number(goalData.earnings_gap || 0).toFixed(2)}</div>
          <div>Trips Completed: {goalData.trips_completed || 0}</div>
        </div>
      )}

      <h3>Trips Today</h3>
      {trips.map((t) => (
        <div key={t.trip_id}>
          {t.trip_id} | {t.distance_km} km | ₹{t.fare}
        </div>
      ))}

      <h3 style={{ marginTop: 30 }}>Earnings Trend</h3>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={earningsSeries}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="timestamp" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="cumulative_earnings" name="Cumulative Earnings" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <h3 style={{ marginTop: 30 }}>Velocity Trend</h3>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={earningsSeries}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="timestamp" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="current_velocity" name="Current Velocity" />
            <Line type="monotone" dataKey="target_velocity" name="Target Velocity" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <h3 style={{ marginTop: 30 }}>Stress Timeline</h3>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={stressData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="stress" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <h3 style={{ marginTop: 30 }}>Live Stress Events</h3>
      {liveEvents.slice(-5).map((e, i) => (
        <div key={i}>
          {e.type} ({e.db} dB)
        </div>
      ))}

      <h3 style={{ marginTop: 30 }}>Flagged Stress Moments</h3>
      {flagged.slice(0, 10).map((f, idx) => (
        <div key={`${f.timestamp}-${idx}`}>
          {f.trip_id} | {f.severity} | {f.explanation}
        </div>
      ))}
    </div>
  )
}



export default Dashboard
