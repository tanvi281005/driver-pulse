// src/Dashboard.jsx
import { useEffect, useState, useRef, useMemo } from "react"
import axios from "axios"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell, 
  RadialBar, 
  RadialBarChart
} from "recharts"

// Needle uses same math as before
function Needle({ value, cx, cy, radius }) {
  // value: 0..100
  const clamped = Math.max(0, Math.min(100, value))
  const angle = 180 * (1 - clamped / 100)
  const rad = (Math.PI / 180) * angle

  const x = cx + radius * Math.cos(rad)
  const y = cy - radius * Math.sin(rad)

  return (
    <g>
      <line
        x1={cx}
        y1={cy}
        x2={x}
        y2={y}
        stroke="#ffffff"
        strokeWidth={3}
        strokeLinecap="round"
      />
      <circle cx={cx} cy={cy} r={6} fill="#ffffff" />
    </g>
  )
}

// helper to draw arcs
function polarToCartesian(cx, cy, r, angleDeg) {
  const angleRad = (angleDeg - 90) * Math.PI / 180.0
  return {
    x: cx + (r * Math.cos(angleRad)),
    y: cy + (r * Math.sin(angleRad))
  }
}

function describeArc(cx, cy, r, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, r, endAngle)
  const end = polarToCartesian(cx, cy, r, startAngle)
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1"
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`
}

// Small helpers
const fmtRupee = (v) => `₹${Number(v || 0).toLocaleString()}`

function SmallKPI({ title, value, subtitle, accent }) {
  return (
    <div style={{
      padding: 18,
      borderRadius: 12,
      background: `linear-gradient(180deg, rgba(255,255,255,0.02), rgba(0,0,0,0.05))`,
      boxShadow: "0 6px 18px rgba(0,0,0,0.45)",
      minWidth: 160
    }}>
      <div style={{fontSize:12, color:"#cbd5e1"}}>{title}</div>
      <div style={{fontSize:22, fontWeight:700, marginTop:6, color: accent || "#f1f5f9"}}>{value}</div>
      {subtitle && <div style={{fontSize:12, color:"#9ca3af", marginTop:6}}>{subtitle}</div>}
    </div>
  )
}

function FlagDot(props){
  // custom dot for line chart - show larger colored dot for flagged points
  const { cx, cy, payload } = props
  if (!cx || !cy) return null
  const val = payload?.stress ?? 0
  const flagged = payload?.flagged
  const color = flagged ? "#ef4444" : (val > 0.6 ? "#f59e0b" : "#60a5fa")
  const r = flagged ? 5 : 3
  return <circle cx={cx} cy={cy} r={r} fill={color} stroke="#0b1220" strokeWidth={1}/>
}

export default function Dashboard({ driver }) {

  const [shiftActive,setShiftActive] = useState(false)
  const [smoothRisk, setSmoothRisk] = useState(0)
  const [trips,setTrips] = useState([])
  const [earnings,setEarnings] = useState([])          // raw earnings list (trip rows)
  const [stressData,setStressData] = useState([])      // array {time, stress, flagged}
  const [liveEvents,setLiveEvents] = useState([])      // in-memory live events

  const [todayStats,setTodayStats] = useState(null)

  const [goalTarget,setGoalTarget] = useState(0)
  const [goalProgress,setGoalProgress] = useState(0)

  const [riskLevel,setRiskLevel] = useState("SAFE")

  const [activeTrip,setActiveTrip] = useState(null)
  const [tripRunning,setTripRunning] = useState(false)

  const intervalRef = useRef(null)

  // UI palette
  const palette = {
    bg: "#071124",
    card: "#0f1724",
    accent1: "#f59e0b", // amber
    accent2: "#b45309", // brown/orange
    accent3: "#ffd166",
    text: "#e6eef8"
  }

  useEffect(()=>{

    loadShiftStatus()

    // poll live events periodically to refresh event list (in case offline queue fills)
    const evPoll = setInterval(()=>{
      if(shiftActive) loadLiveEvents()
    }, 5000)

    return ()=> clearInterval(evPoll)

  },[]) // eslint-disable-line

  // Derived values
  const latestStress = stressData.length ? stressData[stressData.length - 1].stress : 0
  const flaggedCount = liveEvents.length
  const tripsCount = trips.length

  useEffect(() => {
    // smooth needle animation (simple exponential smoothing)
    const id = setInterval(() => {
      setSmoothRisk(prev => {
        const target = latestStress
        return prev + (target - prev) * 0.15
      })
    }, 50)

    return () => clearInterval(id)
  }, [latestStress])

  // compute cumulative earnings series for chart
  const earningsSeries = useMemo(() => {
    if(!earnings || earnings.length === 0) return []
    let cumul = 0
    return earnings.map((r, idx) => {
      const f = Number(r.fare || 0)
      cumul += f
      return { name: String(idx+1), trip: r.trip_id, fare: f, cumul }
    })
  }, [earnings])

  // compute simple driving metrics
  const drivingMetrics = useMemo(() => {
    const avgStress = stressData.length ? (stressData.reduce((s,x)=>s + (x.stress||0), 0) / stressData.length) : 0
    const spikes = liveEvents.filter(e => (Number(e.db)||0) > 85).length
    return {
      avgStress: avgStress,
      events: liveEvents.length,
      spikes,
      trips: trips.length
    }
  }, [stressData, liveEvents, trips])

  // ----------------------------
  // API / load functions
  // ----------------------------
  const loadShiftStatus = async () => {
    try{
      const res = await axios.get(`http://localhost:8000/shift_status/${driver.driver_id}`)
      setShiftActive(res.data.active)
      if(res.data.active){
        // load shift-scoped data
        await Promise.all([loadTrips(), loadEarnings(), loadStats(), loadGoal(), loadLiveEvents()])
      }
    }catch(e){
      console.error("shift status load failed", e)
    }
  }

  const loadTrips = async () => {
    try{
      const res = await axios.get(`http://localhost:8000/driver_trips/${driver.driver_id}`)
      setTrips(res.data || [])
    }catch(e){
      console.error("loadTrips err", e)
    }
  }

  const loadEarnings = async () => {
    try{
      const res = await axios.get(`http://localhost:8000/earnings/${driver.driver_id}`)
      setEarnings(res.data || [])
    }catch(e){
      console.error("loadEarnings err", e)
    }
  }

  const loadStats = async () => {
    try{
      const res = await axios.get(`http://localhost:8000/driver_today_stats/${driver.driver_id}`)
      setTodayStats(res.data)
    }catch(e){
      console.error("loadStats err", e)
    }
  }

  const loadGoal = async () => {
    try{
      const res = await axios.get(`http://localhost:8000/driver_goal/${driver.driver_id}`)
      setGoalTarget(res.data.target || 0)
      setGoalProgress(res.data.progress || 0)
    }catch(e){
      console.error("loadGoal err", e)
    }
  }

  const loadLiveEvents = async () => {
    try{
      const res = await axios.get(`http://localhost:8000/live_events/${driver.driver_id}`)
      setLiveEvents(res.data || [])
    }catch(e){
      console.error("loadLiveEvents err", e)
    }
  }

  // ----------------------------
  // Actions (shift/trip)
  // ----------------------------
  const startShift = async () => {
    try{
      await axios.post(`http://localhost:8000/start_shift/${driver.driver_id}`)
      setShiftActive(true)
      await Promise.all([loadTrips(), loadEarnings(), loadStats(), loadGoal(), loadLiveEvents()])
    }catch(e){
      console.error("startShift", e)
    }
  }

  const endShift = async () => {
    try{
      await axios.post(`http://localhost:8000/end_shift/${driver.driver_id}`)
      setShiftActive(false)
      setTrips([])
      setEarnings([])
      setTodayStats(null)
      setGoalProgress(0)
      setGoalTarget(0)
    }catch(e){
      console.error("endShift", e)
    }
  }

  const startTrip = async () => {
    if(!shiftActive){
      alert("Start shift first")
      return
    }
    try{
      const res = await axios.post(`http://localhost:8000/start_trip/${driver.driver_id}`)
      const tripId = res.data.trip_id
      setStressData([])
      setLiveEvents([])
      setActiveTrip(tripId)
      setTripRunning(true)
      startSimulation(tripId)
    }catch(e){
      console.error("startTrip", e)
    }
  }

  const startSimulation = (tripId) => {
    if(intervalRef.current) return
    intervalRef.current = setInterval(async () => {
      try{
        const res = await axios.get(`http://localhost:8000/trip_step/${tripId}`)
        const audio = res.data.audio || {}
        const stress = res.data.stress || {}
        const stressValue = Number(stress.stress || 0)
        const flagged = !!stress.flagged
        setStressData(prev => {
          const next = [...prev, { time: prev.length, stress: stressValue, flagged }]
          // keep last 200 points
          if(next.length > 400) next.shift()
          return next
        })

        // set risk level
        if(stressValue > 0.75) setRiskLevel("HIGH")
        else if(stressValue > 0.5) setRiskLevel("MODERATE")
        else setRiskLevel("SAFE")

        if(flagged){
          setLiveEvents(prev => {
            const ev = {
              time: prev.length,
              timestamp: audio?.timestamp || new Date().toISOString(),
              type: audio?.audio_classification || "stress",
              db: Number(audio?.audio_level_db || 0),
              risk: stressValue,
              model_used: stress.model_used || ""
            }
            const next = [...prev, ev]
            if(next.length > 500) next.shift()
            return next
          })
        }
      }catch(e){
        console.error("trip_step err", e)
      }
    }, 1000)
  }

  const endTrip = async () => {
    if(intervalRef.current){
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    const earningsInput = prompt("Enter trip earnings")
    try{
      await axios.post(`http://localhost:8000/end_trip/${activeTrip}`, { earnings: parseFloat(earningsInput || 0) })
    }catch(e){
      console.error("endTrip err", e)
    }
    setTripRunning(false)
    setActiveTrip(null)
    // refresh
    await Promise.all([loadTrips(), loadEarnings(), loadStats(), loadGoal(), loadLiveEvents()])
    alert("Trip completed")
  }

  // logout handler (non-destructive: clears common token key and navigates to /login)
  const handleLogout = () => {
    try { localStorage.removeItem('authToken') } catch(e){}
    try { localStorage.removeItem('token') } catch(e){}
    if(window && window.location){
      window.location.href = "/login"
    }
  }

  // ----------------------------
  // UI Helpers
  // ----------------------------
  const riskNumeric = Math.min(1.0, latestStress || 0)

  // heatmap grid from stressData
  const heatCells = (() => {
    const arr = stressData.slice(-64) // last 64 samples
    const grid = []
    const cols = 8
    for(let i=0;i<cols;i++) {
      const row = []
      for(let j=0;j<Math.ceil(arr.length/cols); j++){
        const idx = i + j*cols
        const v = arr[idx] ? arr[idx].stress : 0
        row.push(v)
      }
      grid.push(row)
    }
    return grid
  })()

  // ----------------------------
  // Render
  // ----------------------------
  return (
    <div style={{padding:28, background: palette.bg, minHeight:"100vh", color:palette.text, fontFamily: "Inter, Roboto, system-ui"}}>

      <div style={{display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:18}}>
        <div>
          <h2 style={{color: palette.text, margin:0}}>Welcome {driver.name}</h2>
          <div style={{color:"#94a3b8", fontSize:13, marginTop:6}}>Shift {shiftActive ? "Active" : "Inactive"} • {tripRunning ? "Trip running" : "Idle"}</div>
        </div>

        <div style={{display:"flex", gap:12, alignItems:"center"}}>
          {/* Logout button (non-invasive) */}
          <button
            onClick={handleLogout}
            style={{
              padding:"8px 10px",
              background: "transparent",
              border: "1px solid rgba(255,255,255,0.06)",
              color: palette.text,
              borderRadius:8,
              cursor: "pointer",
              fontWeight:700
            }}
          >
            Logout
          </button>

          {!shiftActive && (
            <button onClick={startShift} style={{padding:"10px 14px", background: "#22c55e", border:"none", borderRadius:8, color:"#071124", fontWeight:700}}>Start Shift</button>
          )}
          {shiftActive && !tripRunning && (
            <button onClick={startTrip} style={{padding:"10px 14px", background: "#06b6d4", border:"none", borderRadius:8, color:"#071124", fontWeight:700}}>Start Trip</button>
          )}
          {tripRunning && (
            <button onClick={endTrip} style={{padding:"10px 14px", background: "#ef4444", border:"none", borderRadius:8, color:"white", fontWeight:700}}>End Trip</button>
          )}
          {shiftActive && !tripRunning && (
            <button onClick={endShift} style={{padding:"10px 14px", background: "#f59e0b", border:"none", borderRadius:8, color:"#071124", fontWeight:700}}>End Shift</button>
          )}
        </div>
      </div>

      {/* KPI row */}
      <div style={{display:"flex", gap:14, marginBottom:20, flexWrap:"wrap"}}>
        <SmallKPI title="Shift Earnings" value={fmtRupee(todayStats?.today_earnings || 0)} subtitle="Earnings this shift" accent={palette.accent1} />
        <SmallKPI title="Predicted End" value={fmtRupee(todayStats?.predicted_end || 0)} subtitle="Forecasted by predictor" accent={palette.accent3} />
        <SmallKPI title="Goal Probability" value={`${Math.round((todayStats?.goal_probability||0)*100)}%`} subtitle="Chance to reach goal" accent={palette.accent2} />
        <SmallKPI title="Trips This Shift" value={tripsCount} subtitle="Completed in shift" />
      </div>

      {/* main grid: gauge + earnings */}
      <div style={{display:"grid", gridTemplateColumns:"360px 1fr", gap:18, marginBottom:20}}>

        {/* Left column: gauge + metrics */}
        <div style={{...cardStyle(palette.card), padding:18, borderRadius:12}}>
          <h3 style={{marginTop:0, marginBottom:8}}>Driver Risk Gauge</h3>

          <div style={{display:"flex", alignItems:"center", gap:12}}>
            <div style={{width:200, height:200}}>
              <ResponsiveContainer width="100%" height="100%">
  <RadialBarChart
    cx="50%"
    cy="100%"
    innerRadius="70%"
    outerRadius="100%"
    startAngle={180}
    endAngle={0}
    data={[{ value: smoothRisk * 100 }]}
  >
    <RadialBar
      dataKey="value"
      fill="#64748b"
      background
      cornerRadius={10}
    />

    <Needle
      value={smoothRisk * 100}
      cx={100}
      cy={190}
      radius={70}
    />

  </RadialBarChart>
</ResponsiveContainer>
            </div>

            <div style={{flex:1}}>
              <div style={{fontSize:24, fontWeight:800, color: palette.text}}>{Math.round(riskNumeric*100)}%</div>
              <div style={{color:"#9ca3af", marginTop:6}}>Latest stress</div>

              <div style={{marginTop:14}}>
                <div style={{fontSize:13, color:"#cbd5e1", marginBottom:6}}>Quick Driving Metrics</div>
                <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:8}}>
                  <div style={{background:"rgba(255,255,255,0.02)", padding:8, borderRadius:8}}>
                    <div style={{fontSize:12, color:"#9ca3af"}}>Avg Stress</div>
                    <div style={{fontWeight:700}}>{(drivingMetrics.avgStress*100).toFixed(0)}%</div>
                  </div>
                  <div style={{background:"rgba(255,255,255,0.02)", padding:8, borderRadius:8}}>
                    <div style={{fontSize:12, color:"#9ca3af"}}>Events</div>
                    <div style={{fontWeight:700}}>{drivingMetrics.events}</div>
                  </div>

                  <div style={{background:"rgba(255,255,255,0.02)", padding:8, borderRadius:8}}>
                    <div style={{fontSize:12, color:"#9ca3af"}}>Noise Spikes</div>
                    <div style={{fontWeight:700}}>{drivingMetrics.spikes}</div>
                  </div>

                  <div style={{background:"rgba(255,255,255,0.02)", padding:8, borderRadius:8}}>
                    <div style={{fontSize:12, color:"#9ca3af"}}>Trips</div>
                    <div style={{fontWeight:700}}>{drivingMetrics.trips}</div>
                  </div>
                </div>
              </div>

            </div>
          </div>

          {/* small heatmap */}
          <div style={{marginTop:12}}>
            <div style={{fontSize:12, color:"#9ca3af", marginBottom:6}}>Stress heat (recent)</div>
            <div style={{display:"grid", gridTemplateColumns:"repeat(8, 1fr)", gap:4}}>
              {heatCells.flat().slice(0,64).map((v, i)=> {
                const color = v > 0.7 ? "#d97706" : (v > 0.45 ? "#f59e0b" : (v > 0.2 ? "#60a5fa" : "#0ea5a4"))
                return <div key={i} style={{height:14, borderRadius:4, background:color, opacity:0.95}} />
              })}
            </div>
          </div>

        </div>

        {/* Right column: earnings chart + progress */}
        <div style={{...cardStyle(palette.card), padding:18, borderRadius:12}}>
          <div style={{display:"flex", alignItems:"center", justifyContent:"space-between"}}>
            <h3 style={{margin:0}}>Earnings Growth</h3>
            <div style={{fontSize:12, color:"#94a3b8"}}>Shift cumulative earnings</div>
          </div>

          <div style={{height:220, marginTop:8}}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={earningsSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)"/>
                <XAxis dataKey="name" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip formatter={(val)=>fmtRupee(val)} />
                <Line type="monotone" dataKey="cumul" stroke="#ffd166" strokeWidth={3} dot={{r:3}}/>
                <Line type="monotone" dataKey="fare" stroke="#60a5fa" strokeWidth={1} dot={false}/>
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* progress bar */}
          <div style={{marginTop:14}}>
            <div style={{display:"flex", justifyContent:"space-between", alignItems:"center"}}>
              <div style={{fontSize:13, color:"#cbd5e1"}}>Goal Progress</div>
              <div style={{fontSize:13, color:"#9ca3af"}}>{fmtRupee((todayStats?.today_earnings||0))} / {fmtRupee(goalTarget||0)}</div>
            </div>

            <div style={{marginTop:8, height:16, background:"rgba(255,255,255,0.03)", borderRadius:12, overflow:"hidden"}}>
              <div style={{
                width: `${(goalProgress||0)*100}%`,
                height:"100%",
                background: `linear-gradient(90deg, ${palette.accent1}, ${palette.accent2})`
              }}/>
            </div>

            <div style={{fontSize:12, color:"#9ca3af", marginTop:8}}>Probability: {(todayStats?.goal_probability*100 || 0).toFixed(1)}%</div>
          </div>

        </div>

      </div>

      {/* Stress timeline big */}
      <div style={{...cardStyle(palette.card), marginBottom:18, padding:18}}>
        <h3 style={{marginTop:0}}>Stress Timeline</h3>
        <div style={{height:300}}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={stressData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)"/>
              <XAxis dataKey="time" stroke="#9ca3af"/>
              <YAxis domain={[0,1]} stroke="#9ca3af" />
              <Tooltip formatter={(v)=> (v*100).toFixed(0) + "%"} />

              
              <Line type="monotone" dataKey="stress" stroke="#fb7185" strokeWidth={2} dot={<FlagDot/>} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div style={{display:"flex", gap:12, marginTop:12}}>
          <div style={{display:"flex", alignItems:"center", gap:8}}>
            <div style={{width:12, height:12, borderRadius:6, background:"#16a34a"}}/>
            <div style={{fontSize:12, color:"#9ca3af"}}>Safe</div>
          </div>
          <div style={{display:"flex", alignItems:"center", gap:8}}>
            <div style={{width:12, height:12, borderRadius:6, background:"#f59e0b"}}/>
            <div style={{fontSize:12, color:"#9ca3af"}}>Moderate</div>
          </div>
          <div style={{display:"flex", alignItems:"center", gap:8}}>
            <div style={{width:12, height:12, borderRadius:6, background:"#ef4444"}}/>
            <div style={{fontSize:12, color:"#9ca3af"}}>High</div>
          </div>
        </div>
      </div>

      {/* lower grid */}
      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:18}}>

        {/* Live events */}
        <div style={{...cardStyle(palette.card), padding:16}}>
          <h3 style={{marginTop:0}}>Live Stress Events</h3>
          {liveEvents.length === 0 && <div style={{opacity:0.6}}>No stress events detected yet</div>}
          <div style={{marginTop:8, display:"flex", flexDirection:"column", gap:8, maxHeight:260, overflowY:"auto"}}>
            {liveEvents.slice().reverse().slice(0,12).map((e,i)=> {
              const risk = Number(e.risk || 0)
              const badge = risk > 0.75 ? {bg:"#ef4444", txt:"#fff"} : (risk > 0.5 ? {bg:"#f59e0b", txt:"#071124"} : {bg:"#22c55e", txt:"#071124"})
              const time = e.timestamp ? (new Date(e.timestamp).toLocaleTimeString()) : ""
              return (
                <div key={i} style={{display:"flex", justifyContent:"space-between", gap:12, alignItems:"center", padding:10, borderRadius:8, background:"rgba(255,255,255,0.01)"}}>
                  <div>
                    <div style={{fontWeight:800}}>{e.type} — {e.db} dB</div>
                    <div style={{fontSize:12, color:"#9ca3af"}}>{time} • model {e.model_used}</div>
                  </div>
                  <div style={{display:"flex", flexDirection:"column", alignItems:"flex-end"}}>
                    <div style={{background: badge.bg, color: badge.txt, padding:"6px 10px", borderRadius:8, fontWeight:800}}>{Math.round((risk||0)*100)}%</div>
                    <div style={{fontSize:11, color:"#94a3b8", marginTop:8}}>{e.timestamp ? new Date(e.timestamp).toLocaleDateString() : ""}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Trips this shift */}
        <div style={{...cardStyle(palette.card), padding:16}}>
          <h3 style={{marginTop:0}}>Trips This Shift</h3>
          <div style={{display:"flex", flexDirection:"column", gap:10}}>
            {trips.length === 0 && <div style={{opacity:0.6}}>No trips yet</div>}
            {trips.map((t, idx) => {
              const fare = Number(t.fare || 0)
              const maxFare = Math.max(...(trips.map(x=>Number(x.fare||0))||[1]))
              const pct = maxFare > 0 ? Math.min(1, fare / maxFare) : 0
              return (
                <div key={t.trip_id || idx} style={{display:"flex", alignItems:"center", gap:12}}>
                  <div style={{flex:1}}>
                    <div style={{fontWeight:700}}>{t.trip_id}</div>
                    <div style={{fontSize:12, color:"#9ca3af"}}>{t.start_datetime ? new Date(t.start_datetime).toLocaleTimeString() : ""}</div>
                  </div>
                  <div style={{width:150}}>
                    <div style={{display:"flex", justifyContent:"space-between", fontSize:13}}>
                      <div style={{color:"#cbd5e1", fontWeight:700}}>{fmtRupee(fare)}</div>
                      <div style={{fontSize:12, color:"#9ca3af"}}>{t.duration_min || "-" } min</div>
                    </div>
                    <div style={{height:8, background:"rgba(255,255,255,0.03)", borderRadius:6, marginTop:6}}>
                      <div style={{width:`${pct*100}%`, height:"100%", background:"linear-gradient(90deg,#f59e0b,#b45309)", borderRadius:6}}/>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* driving metrics + earnings list */}
        <div style={{...cardStyle(palette.card), padding:16}}>
          <h3 style={{marginTop:0}}>Driving Summary</h3>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:10}}>
            <div style={{background:"rgba(255,255,255,0.02)", padding:10, borderRadius:8}}>
              <div style={{fontSize:12, color:"#9ca3af"}}>Avg Stress</div>
              <div style={{fontWeight:700}}>{(drivingMetrics.avgStress*100).toFixed(0)}%</div>
            </div>
            <div style={{background:"rgba(255,255,255,0.02)", padding:10, borderRadius:8}}>
              <div style={{fontSize:12, color:"#9ca3af"}}>Events</div>
              <div style={{fontWeight:700}}>{drivingMetrics.events}</div>
            </div>
            <div style={{background:"rgba(255,255,255,0.02)", padding:10, borderRadius:8}}>
              <div style={{fontSize:12, color:"#9ca3af"}}>Noise spikes</div>
              <div style={{fontWeight:700}}>{drivingMetrics.spikes}</div>
            </div>
            <div style={{background:"rgba(255,255,255,0.02)", padding:10, borderRadius:8}}>
              <div style={{fontSize:12, color:"#9ca3af"}}>Trips</div>
              <div style={{fontWeight:700}}>{drivingMetrics.trips}</div>
            </div>
          </div>

          <div style={{marginTop:12}}>
            <h4 style={{margin:0, fontSize:13}}>Earnings (recent trips)</h4>
            <div style={{marginTop:8}}>
              <ResponsiveContainer width="100%" height={90}>
                <BarChart data={earningsSeries.slice(-8)}>
                  <XAxis dataKey="name" hide />
                  <YAxis hide />
                  <Tooltip formatter={(v)=>fmtRupee(v)} />
                  <Bar dataKey="fare">
                    {earningsSeries.slice(-8).map((entry, idx) => (
                      <Cell key={`c-${idx}`} fill={idx === earningsSeries.length-1 ? "#ffd166" : "#60a5fa"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>

      </div>

    </div>
  )
}

// small centralized card style generator to keep look consistent
function cardStyle(bg){
  return {
    background: bg,
    borderRadius: 12,
    color: "#e6eef8"
  }
}