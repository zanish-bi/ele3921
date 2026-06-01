**Peer review: StudentGig**
*What's good*
•	Honestly this is a lot. Two marketplace flows, contracts with simulated escrow, dispute resolution, notifications, 284 tests, it's hard to believe this is a semester project. It feels like something you'd actually pay to use.
•	The contract model handling two different bid sources cleanly is not an obvious solution. Someone thought about this properly.
•	The payment sync logic, where changing payment status automatically updates the contract, is the kind of thing that quietly causes bugs in most projects. It doesn't here.
•	The admin panel is genuinely good. Colour-coded statuses, bulk payment actions, admin notes visible to both parties. It looks like something a real platform would ship.
•	284 tests. Most groups hand in zero. This alone sets it apart on the code quality side.
•	The README is better than a lot of project reports we've seen. You can clone it, run one script, and have a working app with test data in two minutes.
•	The KYC test button is a clever workaround for demos, shows the feature without making the presentation awkward.

*Improvements*
•	When you try to post a service without KYC, you just get a blank white page that says "KYC verification required to create listings." No styling, no navigation, nothing. The check works fine, it's just not handled gracefully on the frontend. A redirect with a proper error message would fix it and make the app feel a lot more finished.
•	There's no data dump in the repo. The seed command works fine but the brief asks for one specifically. Quick fix before submission.

Overall, this is a really strong project. The data model, the payment logic, the test coverage, it's all really solid. A few rough edges on the frontend but nothing that takes away from how much work clearly went into this.

