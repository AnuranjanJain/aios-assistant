class CareerAdvisor:
    def recommend(self, portfolio, applications, matches):
        recommendations = []
        score = portfolio.get("portfolio_score", 0)
        if score < 75:
            recommendations.append(
                {
                    "category": "portfolio",
                    "priority": 90,
                    "title": "Raise flagship project proof",
                    "rationale": "The portfolio score is below the hiring-ready zone.",
                    "action": {"next": "Add tests, screenshots, README setup, and a release to AiOS."},
                }
            )
        if applications and not any(item.get("status") in {"interview", "offer"} for item in applications):
            recommendations.append(
                {
                    "category": "applications",
                    "priority": 75,
                    "title": "Improve follow-up signal",
                    "rationale": "Applications are tracked but no interview-stage entry is visible yet.",
                    "action": {"next": "Prioritize roles where job match score is above 70 before applying."},
                }
            )
        if matches and max(item.get("overall_score", 0) for item in matches) < 65:
            recommendations.append(
                {
                    "category": "skills",
                    "priority": 70,
                    "title": "Close repeated JD gaps",
                    "rationale": "Recent job matches are not clearing the strong-match threshold.",
                    "action": {"next": "Use missing skill lists from job matches to update the 30-day roadmap."},
                }
            )
        if not recommendations:
            recommendations.append(
                {
                    "category": "career",
                    "priority": 60,
                    "title": "Keep the release rhythm visible",
                    "rationale": "Current evidence is moving in the right direction; consistency will matter now.",
                    "action": {"next": "Ship one meaningful GitHub update and one application batch each week."},
                }
            )
        return recommendations
