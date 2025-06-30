# Scintilla Demo Script - Dashworks Replacement Presentation

**Duration: ~5-6 minutes**  
**Audience: Management (familiar with Dashworks)**  
**Goal: Present Scintilla as a suitable solution for our needs**

---

## 🎬 **Opening Hook** (30 seconds)

> "Hi [Boss Name], I wanted to show you Scintilla - the federated search solution we've been developing. It provides similar functionality to what we had with Dashworks, but addresses our specific requirements, including access to VPN-only systems like Khoros."

**[Screen: Show Scintilla landing page]**

> "As you can see, we already have Google authentication set up, so it integrates with our existing identity management. I'll walk you through the key features - sources and bots work similarly to Dashworks, with some additions to handle our infrastructure constraints."

---

## 🔐 **Local Agent for VPN Access** (1.5 minutes)

**[Screen: Navigate to Sources page with VPN sources visible]**

> "As with Dashworks, we have sources that connect to our various data systems. The key difference is that we needed to access systems behind our VPN, particularly our Khoros Atlassian instance where most of our support data lives."

**[Screen: Show mix of cloud and VPN sources]**

> "We've implemented a local agent that runs inside our network perimeter. This allows us to connect to VPN-only resources while maintaining our security requirements."

> "So we can search across both our internal Jira projects and external cloud sources in a single query."

---

## 🤖 **Bot Configuration with Custom Instructions** (2 minutes)

**[Screen: Navigate to Bots → Create Bot]**

> "The bot system works similarly to Dashworks - these are specialized search configurations for different teams or use cases."

**[Quick form fill]:**
- **Name**: "Support Escalation Assistant"
- **Description**: "Analyzes issues using internal and external data sources"

**[Screen: Add sources with custom instructions]**

> "Like in Dashworks, we can configure which sources each bot uses. We've added the ability to give different instructions to each source within the same bot."

**[Add sources quickly]:**
- **Khoros Jira**: "Focus on P1/P2 tickets, escalation patterns"
- **Support Docs**: "Extract resolution steps, customer-facing solutions"

> "This means the bot can tailor its approach depending on whether it's searching tickets versus documentation."

**[Demo query]:**
> "What are recent P1 authentication issues from Khoros and their resolution patterns?"

**[Screen: Show response with internal + external citations]**

> "As you can see, we get results from both our internal Khoros instance and our documentation sources, with citations linking back to the original sources - similar to how Dashworks worked."

---

## 💡 **Current Implementation** (1 minute)

**[Screen: Stay on results]**

> "We have this running with a pilot group in support. The functionality is familiar to anyone who used Dashworks - natural language search across multiple data sources."

> "The main advantage for us is that it covers our complete knowledge base - both the cloud-accessible tools and the internal systems behind our VPN that Dashworks couldn't reach."

> "Since we've built this internally, we have control over updates, integrations, and how it evolves with our needs."

---

## 🎯 **Next Steps** (30 seconds)

> "The next phase would be expanding this to the broader support organization and connecting additional internal sources as needed."

> "What questions do you have about the implementation or the technical approach?"

---

## 📝 **Streamlined Demo Prep**

### Must-Have Setup:
- [ ] VPN sources configured and working
- [ ] One pre-built support bot ready 
- [ ] Query that shows internal + external data
- [ ] Citation links tested to internal systems
- [ ] Google authentication working and visible

### Key Points to Cover:
1. **Google authentication already integrated**
2. **Similar to Dashworks functionality**
3. **Local agent handles VPN requirements**
4. **Familiar sources and bots concept**  
5. **Complete knowledge base access**

### If Demo Fails:
- Focus on architecture explanation and requirements
- Use screenshots/mockups if live demo breaks
- Emphasize the VPN access capability

---

## 🎥 **Recording Tips**

1. **Stay familiar** - Reference Dashworks concepts they know
2. **Show authentication early** - Demonstrates enterprise readiness
3. **Focus on fit** - How it meets our specific needs
4. **Be practical** - Implementation approach
5. **Stay grounded** - This is a familiar tool adapted for us

---

## ⚡ **Ultra-Short Version** (3 minutes)

For the busiest executives:
1. **Context** (20s) - Dashworks-like solution with Google auth for our infrastructure needs
2. **VPN Access Demo** (1m) - Show internal source connectivity
3. **Bot Query** (1m) - Internal + external data combination  
4. **Implementation** (40s) - Pilot running, meets our requirements 