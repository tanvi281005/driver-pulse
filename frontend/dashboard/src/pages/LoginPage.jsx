import { useState } from "react"
import axios from "axios"
import Dashboard from "./Dashboard"

function LoginPage() {

  const [driverId,setDriverId] = useState("")
  const [driver,setDriver] = useState(null)

  const login = async () => {

    const res = await axios.post("http://localhost:8000/login",{
      driver_id: driverId
    })

    if(res.data.status === "success"){
      setDriver(res.data.driver)
    }else{
      alert("Invalid Driver ID")
    }

  }

  if(driver){
    return <Dashboard driver={driver}/>
  }

  return (

    <div style={{padding:40}}>

      <h2>Driver Login</h2>

      <input
        placeholder="Driver ID"
        value={driverId}
        onChange={(e)=>setDriverId(e.target.value)}
      />

      <button onClick={login}>
        Login
      </button>

    </div>

  )
}

export default LoginPage