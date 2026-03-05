import { useEffect, useState, useRef } from "react"
import axios from "axios"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts"

function Dashboard({driver}){

  const [trips,setTrips] = useState([])
  const [earnings,setEarnings] = useState([])
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

  }


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

export default Dashboard