import { useState, useEffect } from "react"
import axios from "axios"
import Dashboard from "./Dashboard"

function LoginPage() {

  const [driverId, setDriverId] = useState("")
  const [driver, setDriver] = useState(null)

  const title = "Driver Pulse"
  const [displayedTitle, setDisplayedTitle] = useState("")

  // typing animation
  useEffect(() => {

    let i = 0

    const interval = setInterval(() => {
      setDisplayedTitle(title.slice(0, i + 1))
      i++

      if (i === title.length) {
        clearInterval(interval)
      }

    }, 120)

    return () => clearInterval(interval)

  }, [])

  const login = async () => {

    try {

      const res = await axios.post("https://driver-pulse.onrender.com/login", {
        driver_id: driverId
      })

      if (res.data.status === "success") {
        setDriver(res.data.driver)
      } else {
        alert("Invalid Driver ID")
      }

    } catch {
      alert("Server error")
    }

  }

  if (driver) {
    return <Dashboard driver={driver} />
  }

  return (

    <div style={styles.page}>

      <div style={styles.card}>

        <h1 style={styles.title}>
          {displayedTitle}
        </h1>

        <p style={styles.subtitle}>
          Smart analytics for Uber-style driver performance
        </p>

        <input
          style={styles.input}
          placeholder="Enter Driver ID"
          value={driverId}
          onChange={(e) => setDriverId(e.target.value)}
        />

        <button
          style={styles.button}
          onClick={login}
        >
          Login
        </button>

        <div style={styles.footer}>
          Driver Pulse • Real-time stress & earnings insights
        </div>

      </div>

    </div>

  )
}

const styles = {

  page: {
    height: "100vh",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    background: "linear-gradient(135deg,#020617,#0f172a,#1e293b)",
    fontFamily: "Inter, sans-serif"
  },

  card: {
    background: "#0f172a",
    padding: 40,
    borderRadius: 16,
    width: 360,
    boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
    textAlign: "center"
  },

  title: {
    fontSize: 36,
    fontWeight: 800,
    color: "#f59e0b",
    letterSpacing: 1
  },

  subtitle: {
    color: "#94a3b8",
    marginBottom: 30,
    fontSize: 14
  },

  input: {
    width: "100%",
    padding: 12,
    marginBottom: 16,
    borderRadius: 8,
    border: "none",
    outline: "none",
    fontSize: 16,
    background: "#020617",
    color: "#e2e8f0"
  },

  button: {
    width: "100%",
    padding: 12,
    background: "#f59e0b",
    border: "none",
    borderRadius: 8,
    fontWeight: 700,
    fontSize: 16,
    cursor: "pointer",
    transition: "0.2s"
  },

  footer: {
    marginTop: 20,
    fontSize: 12,
    color: "#64748b"
  }

}

export default LoginPage