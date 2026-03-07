// src/Dashboard.jsx

import { useEffect, useState, useRef } from "react"
import axios from "axios"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts"

function Dashboard({driver}){

  const [trips,setTrips] = useState([])
  const [earnings,setEarnings] = useState([])
  const [stressData,setStressData] = useState([])
  const [liveEvents,setLiveEvents] = useState([])
  const [todayStats,setTodayStats] = useState(null)
  const [riskLevel,setRiskLevel] = useState("SAFE")

  const [activeTrip,setActiveTrip] = useState(null)
  const [tripRunning,setTripRunning] = useState(false)

  const intervalRef = useRef(null)

  useEffect(()=>{

    loadTrips()
    loadEarnings()
    loadStats()

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

  const loadStats = async () => {

    const res = await axios.get(
      `http://localhost:8000/driver_today_stats/${driver.driver_id}`
    )

    setTodayStats(res.data)

  }

  const startTrip = async () => {

    const res = await axios.post(
      `http://localhost:8000/start_trip/${driver.driver_id}`
    )

    const tripId = res.data.trip_id

    setStressData([])
    setLiveEvents([])

    setActiveTrip(tripId)
    setTripRunning(true)

    startSimulation(tripId)

  }

  const startSimulation = (tripId) => {

    intervalRef.current = setInterval(async () => {

      const res = await axios.get(
        `http://localhost:8000/trip_step/${tripId}`
      )

      const audio = res.data.audio
      const stress = res.data.stress
      console.log("Stress step:", stress)
      if(!stress) return

      const stressValue = stress.stress || 0

      setStressData(prev => [
        ...prev,
        {
          time: prev.length,
          stress: stressValue
        }
      ])

      // Risk meter
      if(stressValue > 0.75) setRiskLevel("HIGH")
      else if(stressValue > 0.5) setRiskLevel("MODERATE")
      else setRiskLevel("SAFE")

      if(stress.flagged){

        setLiveEvents(prev => [
          ...prev,
          {
            time: prev.length,
            type: audio?.audio_classification || "risk",
            db: audio?.audio_level_db || 0,
            risk: stressValue,
            model_used: stress.model_used
          }
        ])

      }

    },1000)

  }

  const endTrip = async () => {

    clearInterval(intervalRef.current)

    const earningsInput = prompt("Enter trip earnings")

    await axios.post(
      `http://localhost:8000/end_trip/${activeTrip}`,
      { earnings: parseFloat(earningsInput || 0) }
    )

    setTripRunning(false)
    setActiveTrip(null)

    loadTrips()
    loadEarnings()
    loadStats()

    alert("Trip completed")

  }

  const card = {
    background:"#0f1724",
    padding:"20px",
    borderRadius:"10px",
    boxShadow:"0 2px 8px rgba(0,0,0,0.3)",
    color:"#e6eef8"
  }

  const riskColor = {
    SAFE:"#22c55e",
    MODERATE:"#f59e0b",
    HIGH:"#ef4444"
  }

  return(

    <div style={{padding:40, background:"#0b1220", minHeight:"100vh", color:"#e6eef8"}}>

      <h2 style={{color:"#cfe8ff"}}>Welcome {driver.name}</h2>

      <div style={{marginBottom:20}}>

        {!tripRunning && (
          <button onClick={startTrip} style={{padding:"8px 12px", background:"#06b6d4", border:"none", borderRadius:6}}>
            Start Trip
          </button>
        )}

        {tripRunning && (
          <button onClick={endTrip} style={{padding:"8px 12px", background:"#ef4444", border:"none", borderRadius:6}}>
            End Trip
          </button>
        )}

      </div>

      {/* DRIVER RISK METER */}

      <div style={{...card, marginBottom:20}}>

        <h3>Driver Risk Level</h3>

        <div style={{
          fontSize:28,
          fontWeight:"bold",
          color:riskColor[riskLevel]
        }}>
          {riskLevel}
        </div>

      </div>


      {/* STATS */}

      <div style={{
        display:"grid",
        gridTemplateColumns:"1fr 2fr",
        gap:"20px",
        marginBottom:"20px"
      }}>

        <div style={card}>

          <h3>Today's Stats</h3>

          <p>Today's Earnings: ₹{todayStats?.today_earnings || 0}</p>

          <p>Predicted End: ₹{todayStats?.predicted_end || 0}</p>

          <p>Goal Probability: {(todayStats?.goal_probability*100 || 0).toFixed(1)}%</p>

        </div>


        <div style={card}>

          <h3>Earnings vs Prediction</h3>

          <LineChart
            width={500}
            height={250}
            data={[
              {name:"Current",value:todayStats?.today_earnings || 0},
              {name:"Predicted",value:todayStats?.predicted_end || 0}
            ]}
          >

            <CartesianGrid strokeDasharray="3 3"/>

            <XAxis dataKey="name" stroke="#e6eef8"/>

            <YAxis stroke="#e6eef8"/>

            <Tooltip/>

            <Line type="monotone" dataKey="value" stroke="#60a5fa"/>

          </LineChart>

        </div>

      </div>


      {/* STRESS GRAPH */}

      <div style={{...card, marginBottom:"20px"}}>

        <h3>Stress Timeline</h3>

        <LineChart width={900} height={300} data={stressData}>

          <CartesianGrid strokeDasharray="3 3"/>

          <XAxis dataKey="time" stroke="#e6eef8"/>

          <YAxis stroke="#e6eef8"/>

          <Tooltip/>

          <Line type="monotone" dataKey="stress" stroke="#fb7185"/>

        </LineChart>

      </div>


      {/* LOWER GRID */}

      <div style={{
        display:"grid",
        gridTemplateColumns:"1fr 1fr 1fr",
        gap:"20px"
      }}>

        <div style={card}>

          <h3>Live Stress Events</h3>

          {liveEvents.length === 0 && (
            <div style={{opacity:0.6}}>No stress events detected yet</div>
          )}

          {liveEvents.slice(-10).map((e,i)=>(

            <div key={i} style={{
              padding:8,
              borderBottom:"1px solid rgba(255,255,255,0.06)"
            }}>

              <div style={{fontWeight:700}}>
                {e.type} — {e.db} dB
              </div>

              <div style={{fontSize:12}}>
                risk {(e.risk*100).toFixed(0)}% — model {e.model_used}
              </div>

            </div>

          ))}

        </div>


        <div style={card}>

          <h3>Trips Today</h3>

          {trips.map(t => (
            <div key={t.trip_id}>
              {t.trip_id} | ₹{t.fare || "-"}
            </div>
          ))}

        </div>


        <div style={card}>

          <h3>Earnings</h3>

          {earnings.map(e => (
            <div key={e.trip_id}>
              {e.trip_id} : ₹{e.fare}
            </div>
          ))}

        </div>

      </div>

    </div>

  )

}

export default Dashboard