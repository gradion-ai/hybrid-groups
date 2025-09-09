# Introduction

*Hybrid Groups* integrates human team collaboration with AI agents. Unlike typical AI applications built for single-user interaction, *Hybrid Groups* enables AI agents to have conversations with multiple users simultaneously, recognizing each user’s identity and respecting their unique preferences and permissions. 

<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; height: auto;">
    <iframe src="https://www.youtube.com/embed/OxOmRsNin4o" frameborder="0" allowfullscreen style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"></iframe>
</div>

Agents can also proactively support team discussions by contributing relevant information or initiating helpful actions. *Hybrid Groups* currently supports Slack and GitHub as team collaboration platforms, and is extensible to other platforms. 

!!! Tip "Tutorial"

    Check the [tutorial](tutorial.md) for a feature overview with examples.
<div class="image-row">
  <div class="image-item">
    <div class="image-zoom">
      <a href="images/overview/overview-1.png" target="_blank"><img src="images/overview/overview-1.png" class="thumbnail"></a>
      <a href="images/overview/overview-1.png" target="_blank" class="large-link"><img src="images/overview/overview-1.png" class="large"></a>
    </div>
    <p class="caption"><b>Figure 1:</b> A <i>Hybrid Groups</i> thread in Slack.</p>
  </div>
  <div class="image-item">
    <div class="image-zoom">
      <a href="images/overview/overview-3.png" target="_blank"><img src="images/overview/overview-3-crop.png" class="thumbnail"></a>
      <a href="images/overview/overview-3.png" target="_blank" class="large-link"><img src="images/overview/overview-3.png" class="large"></a>
    </div>
    <p class="caption"><b>Figure 2:</b> A <i>Hybrid Groups</i> thread in GitHub.</p>
  </div>
</div>

Users and agents collaborate in group sessions. A group session corresponds to a thread in Slack or an issue in GitHub. The system analyzes group messages to determine if an agent should be activated, but users may also invoke agents directly. All agents have full group session context, including messages and members.
