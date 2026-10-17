# PlanIT Control - Sperry Tech challenge brief

Text transcribed from the sponsor's challenge brief (PlanIT Control, Sperry Tech, SwampHacks XII). It is kept here so every teammate and coding assistant works from the same requirements. If this copy and the original disagree, the original governs. Only wording and layout were adjusted; nothing was added to the requirements.

## Scenario

It is 6:45 AM, in August, at a remote construction side in the middle of the Everglades. The crew is about to start installing a temporary road for equipment to mobilize in to build a new transmission line to power to the city. By noon, the heat index will surpass 110°F. Afternoon thunderstorms are building to the west, and the ground has been soaking up rain for a week, causing boots to be covered in mud and vehicles to get stuck in the muck. Someone saw a gator in the swamp next to the jobsite yesterday, but that information lives in one person's text messages.

Every one of those hazards is knowable ahead of time. The problem is that the data is scattered across a dozen apps and agencies; nobody turns it into a decision, and go/no-go calls are often made on just instinct the morning of.

PlanIT Control fixes that. Your team will build a platform that knows exactly where each job site is, continuously pulls the environmental conditions that matter to the people working there, warns crews the moment conditions become dangerous, and uses machine learning to analyze historical data, and then score and forecast each site's hazard level so supervisors can plan ahead instead of reacting.

## The challenge

Build a real-time web or mobile platform that watches the environment around every job site to keep utility field crews safe by bringing scattered hazard data together:

- **One combined risk picture per site:** Using at least 50 actual power plant locations, the platform should combine planet conditions like weather, extreme heat, lightning, flooding, wildfire, soil saturation, and wildlife sightings into one picture per site.
- **Instant alerts when conditions turn dangerous:** It should warn crews as soon as risk spikes. For example:
  - **Lightning:** any strike within 10 miles triggers a stop-work alert with a 30-minute all-clear countdown that restarts with each new strike.
  - **Flooding:** sites along rivers, such as the Mississippi, get a flood-risk warning after a night of heavy rain.
- **Daily next-day safety briefing:** every evening at 6 PM local time, it sends a next-day safety report.
- **Crew hazard reporting:** Just as a driver taps to report a crash or debris on the road, a crew member can snap a photo, pin a hazard to the site map, and share instantly to not only his team, but contribute to a database of location hazards for future project owners.
- **Supervisor PlanIt Dashboard:** a map that ranks sites by risk, showing supervisors where to focus attention and resources first.
- **Hazard index (0-10):** A machine learning (ML) model trained on historical weather and environmental data tied to the hazards on-site workers actually face.

## Helpful resources (optional)

These are starting points if you want them. You're free to use any data sources or tools you prefer.

- **EIA-860M:** A monthly U.S. government list of power plants with coordinates, utility, county, and plant type. It's a good source for real job site locations. (Heads up: the link in the original challenge doc points to an FPL project page, not the EIA dataset.)
- **NOAA Storm Events Database:** Historical records of severe weather events, useful for training the hazard model.
- **Iowa Environmental Mesonet:** An archive of historical National Weather Service warnings.
- **OSHA Severe Injury Reports:** Workplace incident data with locations, useful for labeling real-world hazard outcomes.
- **National Levee Database (NLD):** USACE's national map of levees, floodwalls, and their condition, with a Boreholes layer showing where geotechnical soil borings were drilled along levee systems. Useful for subsurface soil conditions near flood-control structures.
- **NOAA Tides & Currents:** NOAA's official source for real-time and historical water levels, tide predictions, currents, and sea level trends from monitoring stations along U.S. coasts and the Great Lakes. Useful for tidal datums, flooding thresholds, and water level conditions near coastal or waterfront sites.
- **FEMA Flood Map Service Center (MSC):** FEMA's official source for flood hazard maps, including Flood Insurance Rate Maps (FIRMs), flood zone designations, and base flood elevations for any U.S. address. Useful for checking whether a site is in a regulated floodplain and how high flood risk is.
